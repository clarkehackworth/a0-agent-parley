"""Orchestrate the @mention use case.

The only file where Agent Zero internals (AgentContext, UserMessage) and
chat platform abstractions meet. Everything above this (listener) depends on
the ChatPlatform port; everything below (Agent Zero) is pure application logic.

Flow:
  1. Authorize commands via DM challenge if a password is configured.
  2. Build a context window (channel history) for the agent to reason over.
  3. Send a "Working…" reply so the user sees immediate feedback.
  4. Start a spinner that edits that reply with live step summaries.
  5. Hand the prompt to an ephemeral AgentContext and let it run.
     Step updates and the final reply are sent by extensions in the
     process_chain lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import re

from usr.plugins.parley.helpers.revolt_constants import (
    CTX_REVOLT_CHANNEL_ID,
    CTX_ORIGINAL_MSG_ID,
    CTX_WORKING_MSG_ID,
    CTX_WORKING_LINES,
    CTX_SPINNER_TASK,
    MAX_MSG_BODY,
)

logger = logging.getLogger("revolt_mention")

_SPINNER_FRAMES = "⣾⣽⣻⢿⡿⣟⣯⣷"

_MENTION_RE = re.compile(r"<@[A-Z0-9]+>", re.IGNORECASE)

_KEYWORD_SYSTEM_PROMPT = (
    "You turn a chat question into search keywords for finding related past "
    "messages in a channel. Reply with ONLY 2-4 lowercase keywords (single "
    "words), separated by spaces. No punctuation, no explanation."
)


async def handle_mention(
    channel_id: str,
    author_id: str,
    author: str,
    content: str,
    original_msg_id: str,
) -> None:
    """Process a bot @mention without creating a persistent per-channel chat."""
    from usr.plugins.parley.infrastructure.revolt.revolt_config import load_revolt_config
    from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
    from usr.plugins.parley.core.context_config import ContextWindowConfig
    from usr.plugins.parley.core.context_window import build_context_window
    from usr.plugins.parley.core.formatting import format_message
    from usr.plugins.parley.helpers import revolt_sent_ids as sent_ids

    # Agent Zero internals — kept lazy to avoid import-time failures at plugin load.
    from agent import AgentContext, AgentContextType, UserMessage
    from initialize import initialize_agent

    clean_content = _MENTION_RE.sub("", content).strip()
    cfg = load_revolt_config()
    platform = get_platform()

    # Commands authorization
    restriction = ""
    if not cfg.get("enable_commands", False):
        restriction = (
            "IMPORTANT: Shell/system commands are disabled for chat-triggered requests. "
            "Do not execute any shell, terminal, or system commands."
        )
    elif (cfg.get("commands_password") or "").strip():
        password = cfg["commands_password"].strip()
        granted = await _dm_auth(platform, "revolt", author_id, author, channel_id, original_msg_id, password)
        if not granted:
            return

    config = initialize_agent()
    ctx = AgentContext(config, name=f"@mention/{original_msg_id[:8]}", type=AgentContextType.BACKGROUND)
    ctx.data[CTX_REVOLT_CHANNEL_ID] = channel_id
    ctx.data[CTX_ORIGINAL_MSG_ID] = original_msg_id

    search_terms = await _search_keywords(ctx.agent0, clean_content)
    transcript = ""
    try:
        win_cfg = ContextWindowConfig.from_dict({**cfg, "recent_limit": cfg.get("recent_limit", 15)})
        merged, user_map, _ = await build_context_window(
            platform,
            channel_id,
            config=win_cfg,
            search_terms=search_terms,
            bot_id=cfg.get("bot_id", ""),
        )
        transcript = _format_transcript(merged, user_map, format_message, exclude_id=original_msg_id)
    except Exception as e:
        logger.warning("Could not build channel context: %s", e)

    working_msg_id = ""
    try:
        status = "⚙️ Working on it…"
        sent_ids.mark_pending(channel_id, status)
        result = await platform.send_reply(channel_id, status, original_msg_id)
        if isinstance(result, dict) and "_id" in result:
            working_msg_id = result["_id"]
            sent_ids.record(working_msg_id)
    except Exception as e:
        logger.warning("Could not send working message: %s", e)

    if working_msg_id:
        ctx.data[CTX_WORKING_MSG_ID] = working_msg_id
        ctx.data[CTX_WORKING_LINES] = ["⚙️ Working on it…"]
        ctx.data[CTX_SPINNER_TASK] = asyncio.create_task(
            _spinner(platform, channel_id, working_msg_id, ctx.data)
        )

    ctx.communicate(
        UserMessage(message=_build_prompt(channel_id, author, clean_content, transcript, restriction))
    )


async def _dm_auth(platform, platform_name, author_id, author_display,
                   channel_id, reply_msg_id, password) -> bool:
    """Send a DM password challenge. Returns True if the user confirms in time."""
    from usr.plugins.parley.helpers.dm_auth import create_challenge, wait_for_challenge, cancel_challenge

    try:
        await platform.send_reply(
            channel_id,
            "🔐 Check your DMs to authorize this command.",
            reply_msg_id,
        )
    except Exception:
        pass

    try:
        await platform.send_dm(
            author_id,
            "🔐 Reply with the password to authorize the command you just requested. You have 2 minutes.",
        )
    except Exception as e:
        logger.warning("Could not send DM for auth to %s: %s", author_id, e)
        try:
            await platform.send_reply(
                channel_id,
                "❌ Could not send you a DM to confirm the command. Commands not executed.",
                reply_msg_id,
            )
        except Exception:
            pass
        return False

    create_challenge(platform_name, author_id, password)
    granted = await wait_for_challenge(platform_name, author_id)

    if not granted:
        try:
            await platform.send_reply(
                channel_id,
                f"⏱️ {author_display}: Authorization timed out. Command not executed.",
                reply_msg_id,
            )
        except Exception:
            pass

    return granted


async def _spinner(platform, channel_id: str, msg_id: str, context_data: dict) -> None:
    """Edit the working message with a rotating spinner every second.

    Runs until cancelled; auto-stops after 5 minutes as a safety net.
    """
    i = 0
    try:
        while i < 300:  # ponytail: 5-min ceiling so errors don't spin forever
            await asyncio.sleep(1)
            lines = list(context_data.get(CTX_WORKING_LINES) or [])
            frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
            header = f"{frame} Working on it…"
            body = header if not lines else "\n".join([header] + lines[1:])
            while len(body) > MAX_MSG_BODY and len(lines) > 2:
                lines.pop(1)
                body = "\n".join([header] + lines[1:])
            try:
                await platform.edit_message(channel_id, msg_id, body)
            except Exception as e:
                logger.debug("Spinner edit skipped: %s", e)
            i += 1
    except asyncio.CancelledError:
        pass


async def _search_keywords(agent, clean_content: str) -> list[str] | None:
    """Use the utility model to derive backfill search keywords; falls back to heuristic."""
    from usr.plugins.parley.core.keywords import extract_keywords
    from usr.plugins.parley.core.models import Message

    if not clean_content:
        return None
    try:
        resp = await agent.call_utility_model(
            system=_KEYWORD_SYSTEM_PROMPT,
            message=clean_content,
            background=True,
        )
        terms = _parse_keywords(resp)
        if terms:
            return terms
    except Exception as e:
        logger.warning("Utility keyword extraction failed, using heuristic: %s", e)
    return extract_keywords([Message(id="", author_id="", content=clean_content)]) or None


def _parse_keywords(resp: str, top_n: int = 4) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", (resp or "").lower())[:top_n]


def _format_transcript(messages: list, user_map: dict, fmt_fn, exclude_id: str = "") -> str:
    lines = []
    for msg in messages:
        if exclude_id and msg.id == exclude_id:
            continue
        lines.append(fmt_fn(msg, user_map))
    return "\n".join(lines)


def _build_prompt(channel_id: str, author: str, clean_content: str, transcript: str, restriction: str = "") -> str:
    parts = [f"[Parley | channel={channel_id}]"]
    if restriction:
        parts[0] += f"\n{restriction}"
    if transcript:
        parts.append(
            "Recent channel context (for reference; may be unrelated to the question):\n"
            + transcript
        )
    parts.append(f"{author} mentioned you and asks:\n{clean_content}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    assert _parse_keywords("deploy window schedule") == ["deploy", "window", "schedule"]
    assert _parse_keywords('Keywords: "deploy", window!') == ["keywords", "deploy", "window"]
    assert _parse_keywords("", top_n=4) == []
    assert _parse_keywords("a an the deployment of") == ["the", "deployment"]
    print("ok")

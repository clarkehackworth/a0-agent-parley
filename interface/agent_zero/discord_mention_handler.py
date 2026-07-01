"""Orchestrate the Discord @mention use case.

Flow:
  1. Authorize commands via DM challenge if a password is configured.
  2. Build recent channel context for the agent.
  3. Send a "Working…" reply so the user sees immediate feedback.
  4. Hand the prompt to an ephemeral AgentContext and let it run.
     The agent calls discord_send to deliver its response.
"""

from __future__ import annotations

import asyncio
import logging
import re

from usr.plugins.parley.helpers.discord_constants import (
    CTX_DISCORD_CHANNEL_ID,
    CTX_DISCORD_ORIGINAL_MSG_ID,
    CTX_DISCORD_WORKING_MSG_ID,
    CTX_DISCORD_WORKING_LINES,
    CTX_DISCORD_SPINNER_TASK,
    DISCORD_MAX_MSG_BODY,
)

logger = logging.getLogger("discord_mention")

_SPINNER_FRAMES = "⣾⣽⣻⢿⡿⣟⣯⣷"
_MENTION_RE = re.compile(r"<@!?[0-9]+>", re.IGNORECASE)


async def handle_mention(
    channel_id: str,
    author_id: str,
    author: str,
    content: str,
    original_msg_id: str,
) -> None:
    """Process a Discord bot @mention in a background agent context."""
    from usr.plugins.parley.infrastructure.discord.discord_config import load_discord_config
    from usr.plugins.parley.infrastructure.discord.discord_platform import get_platform
    from agent import AgentContext, AgentContextType, UserMessage
    from initialize import initialize_agent

    clean_content = _MENTION_RE.sub("", content).strip()
    cfg = load_discord_config()
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
        granted = await _dm_auth(platform, "discord", author_id, author, channel_id, original_msg_id, password)
        if not granted:
            return

    config = initialize_agent()
    ctx = AgentContext(
        config,
        name=f"discord/@mention/{original_msg_id[:8]}",
        type=AgentContextType.BACKGROUND,
    )
    ctx.data[CTX_DISCORD_CHANNEL_ID] = channel_id
    ctx.data[CTX_DISCORD_ORIGINAL_MSG_ID] = original_msg_id

    # Send "Working…" reply, then start spinner
    working_msg_id = ""
    try:
        result = await platform.send_reply(channel_id, "⚙️ Working on it…", original_msg_id)
        working_msg_id = result.get("id", "")
    except Exception as e:
        logger.warning("Could not send Discord working message: %s", e)

    if working_msg_id:
        ctx.data[CTX_DISCORD_WORKING_MSG_ID] = working_msg_id
        ctx.data[CTX_DISCORD_WORKING_LINES] = ["⚙️ Working on it…"]
        ctx.data[CTX_DISCORD_SPINNER_TASK] = asyncio.create_task(
            _spinner(platform, channel_id, working_msg_id, ctx.data)
        )

    transcript = await _recent_transcript(platform, channel_id, cfg, original_msg_id)
    ctx.communicate(UserMessage(message=_build_prompt(channel_id, author, clean_content, transcript, restriction)))


async def _dm_auth(platform, platform_name, author_id, author_display,
                   channel_id, reply_msg_id, password) -> bool:
    """Send a DM password challenge. Returns True if the user confirms in time."""
    from usr.plugins.parley.helpers.dm_auth import create_challenge, wait_for_challenge

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
    # ponytail: no step extension for Discord yet; spinner shows activity without detail
    i = 0
    try:
        while i < 300:
            await asyncio.sleep(1)
            frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
            lines = list(context_data.get(CTX_DISCORD_WORKING_LINES) or [])
            header = f"{frame} Working on it…"
            body = header if not lines else "\n".join([header] + lines[1:])
            while len(body) > DISCORD_MAX_MSG_BODY and len(lines) > 2:
                lines.pop(1)
                body = "\n".join([header] + lines[1:])
            try:
                await platform.edit_message(channel_id, msg_id, body)
            except Exception as e:
                logger.debug("Discord spinner edit skipped: %s", e)
            i += 1
    except asyncio.CancelledError:
        pass


async def _recent_transcript(platform, channel_id: str, cfg: dict, exclude_id: str) -> str:
    try:
        limit = min(cfg.get("recent_limit", 15), 50)
        messages, user_map = await platform.fetch_messages(channel_id, limit=limit)
        lines = []
        for m in reversed(messages):
            if m.id == exclude_id:
                continue
            author_name = user_map.get(m.author_id, m.author_id[:8] if m.author_id else "?")
            lines.append(f"[{author_name}] {m.content}")
        return "\n".join(lines)
    except Exception:
        return ""


def _build_prompt(channel_id: str, author: str, content: str, transcript: str, restriction: str = "") -> str:
    header = f"[Discord | channel={channel_id}]\nUse the discord_send tool to reply in this channel."
    if restriction:
        header += f"\n{restriction}"
    parts = [header]
    if transcript:
        parts.append("Recent channel context:\n" + transcript)
    parts.append(f"{author} mentioned you and asks:\n{content}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    assert _MENTION_RE.sub("", "<@123456> hello") == " hello"
    assert _MENTION_RE.sub("", "<@!123456> hi") == " hi"
    print("ok discord_mention_handler")

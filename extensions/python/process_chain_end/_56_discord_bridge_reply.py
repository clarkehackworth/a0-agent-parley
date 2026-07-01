"""After each agent chain, send the response back to the bridged Discord channel."""

from __future__ import annotations

import asyncio

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.errors import format_error
from agent import AgentContext, LoopData

from usr.plugins.parley.helpers.discord_constants import (
    CTX_DISCORD_CHANNEL_ID,
    CTX_DISCORD_ORIGINAL_MSG_ID,
    CTX_DISCORD_WORKING_MSG_ID,
    CTX_DISCORD_WORKING_LINES,
    CTX_DISCORD_SPINNER_TASK,
    DISCORD_MAX_MSG_LEN,
)


class DiscordBridgeReply(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        context = self.agent.context
        channel_id = context.data.get(CTX_DISCORD_CHANNEL_ID)
        if not channel_id:
            return

        try:
            if context.data.pop("discord_send_used", False):
                return

            response = _last_response(context)
            if not response:
                return

            original_msg_id = context.data.get(CTX_DISCORD_ORIGINAL_MSG_ID)

            from usr.plugins.parley.infrastructure.discord.discord_platform import get_platform
            from usr.plugins.parley.core.message_split import split_message

            platform = get_platform()
            try:
                for chunk in split_message(response, DISCORD_MAX_MSG_LEN):
                    if original_msg_id:
                        await platform.send_reply(channel_id, chunk, original_msg_id, mention=True)
                    else:
                        await platform.send_message(channel_id, chunk)
            except Exception as e:
                PrintStyle.error(f"Discord bridge reply: {format_error(e)}")
        finally:
            await _stop_spinner(context)


def _last_response(context: AgentContext) -> str:
    with context.log._lock:
        logs = list(context.log.logs)
    for item in reversed(logs):
        if item.type == "response":
            return (item.content or "").strip()
    return ""


async def _stop_spinner(context: AgentContext) -> None:
    task = context.data.pop(CTX_DISCORD_SPINNER_TASK, None)
    if not task:
        return

    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    working_msg_id = context.data.get(CTX_DISCORD_WORKING_MSG_ID)
    channel_id = context.data.get(CTX_DISCORD_CHANNEL_ID)
    if not working_msg_id or not channel_id:
        return

    lines = list(context.data.get(CTX_DISCORD_WORKING_LINES) or [])
    body = "\n".join(["✅ Done"] + lines[1:]) if lines else "✅ Done"
    try:
        from usr.plugins.parley.infrastructure.discord.discord_platform import get_platform
        await get_platform().edit_message(channel_id, working_msg_id, body)
    except Exception as e:
        PrintStyle.error(f"Discord spinner stop: {e}")

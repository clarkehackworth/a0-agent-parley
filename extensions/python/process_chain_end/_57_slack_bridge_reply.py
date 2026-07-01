"""After each agent chain, send the response back to the bridged Slack channel."""

from __future__ import annotations

import asyncio

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.errors import format_error
from agent import AgentContext, LoopData

from usr.plugins.parley.helpers.slack_constants import (
    CTX_SLACK_CHANNEL_ID,
    CTX_SLACK_ORIGINAL_MSG_TS,
    CTX_SLACK_WORKING_MSG_TS,
    CTX_SLACK_WORKING_LINES,
    CTX_SLACK_SPINNER_TASK,
    SLACK_MAX_MSG_LEN,
)


class SlackBridgeReply(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        context = self.agent.context
        channel_id = context.data.get(CTX_SLACK_CHANNEL_ID)
        if not channel_id:
            return

        try:
            if context.data.pop("slack_send_used", False):
                return

            response = _last_response(context)
            if not response:
                return

            original_ts = context.data.get(CTX_SLACK_ORIGINAL_MSG_TS)

            from usr.plugins.parley.infrastructure.slack.slack_platform import get_platform
            from usr.plugins.parley.core.message_split import split_message

            platform = get_platform()
            try:
                for chunk in split_message(response, SLACK_MAX_MSG_LEN):
                    # Reply in thread using the original message's ts
                    if original_ts:
                        await platform.send_reply(channel_id, chunk, original_ts)
                    else:
                        await platform.send_message(channel_id, chunk)
            except Exception as e:
                PrintStyle.error(f"Slack bridge reply: {format_error(e)}")
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
    task = context.data.pop(CTX_SLACK_SPINNER_TASK, None)
    if not task:
        return

    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    working_ts = context.data.get(CTX_SLACK_WORKING_MSG_TS)
    channel_id = context.data.get(CTX_SLACK_CHANNEL_ID)
    if not working_ts or not channel_id:
        return

    lines = list(context.data.get(CTX_SLACK_WORKING_LINES) or [])
    body = "\n".join(["✅ Done"] + lines[1:]) if lines else "✅ Done"
    try:
        from usr.plugins.parley.infrastructure.slack.slack_platform import get_platform
        await get_platform().edit_message(channel_id, working_ts, body)
    except Exception as e:
        PrintStyle.error(f"Slack spinner stop: {e}")

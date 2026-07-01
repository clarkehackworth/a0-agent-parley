"""After each agent chain, send the response back to the bridged Revolt channel."""

from __future__ import annotations

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.errors import format_error
from agent import AgentContext, LoopData

from usr.plugins.parley.helpers.revolt_constants import (
    CTX_REVOLT_CHANNEL_ID,
    CTX_ORIGINAL_MSG_ID,
    CTX_WORKING_MSG_ID,
    CTX_WORKING_LINES,
    CTX_SPINNER_TASK,
    MAX_MSG_LEN,
)


class RevoltBridgeReply(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        context = self.agent.context
        channel_id = context.data.get(CTX_REVOLT_CHANNEL_ID)
        if not channel_id:
            return

        try:
            if context.data.pop("parley_send_used", False):
                return

            response = _last_response(context)
            if not response:
                return

            original_msg_id = context.data.get(CTX_ORIGINAL_MSG_ID)

            from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
            from usr.plugins.parley.helpers import revolt_sent_ids as sent_ids
            from usr.plugins.parley.core.message_split import split_message

            platform = get_platform()
            try:
                for chunk in split_message(response, MAX_MSG_LEN):
                    sent_ids.mark_pending(channel_id, chunk)
                    if original_msg_id:
                        sent = await platform.send_reply(channel_id, chunk, original_msg_id, mention=True)
                    else:
                        sent = await platform.send_message(channel_id, chunk)
                    if isinstance(sent, dict) and "_id" in sent:
                        sent_ids.record(sent["_id"])
            except Exception as e:
                PrintStyle.error(f"Revolt bridge reply: {format_error(e)}")
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
    """Cancel the spinner task and update the working message to 'Done'."""
    import asyncio

    task = context.data.pop(CTX_SPINNER_TASK, None)
    if not task:
        return

    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    working_msg_id = context.data.get(CTX_WORKING_MSG_ID)
    channel_id = context.data.get(CTX_REVOLT_CHANNEL_ID)
    if not working_msg_id or not channel_id:
        return

    lines = list(context.data.get(CTX_WORKING_LINES) or [])
    header = "✅ Done"
    body = header if not lines else "\n".join([header] + lines[1:])
    try:
        from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
        await get_platform().edit_message(channel_id, working_msg_id, body)
    except Exception as e:
        PrintStyle.error(f"Revolt spinner stop: {e}")

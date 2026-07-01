"""revolt_send — post a message to a Revolt channel."""

from __future__ import annotations

from helpers.tool import Tool, Response
from usr.plugins.parley.core.message_split import split_message
from usr.plugins.parley.helpers.revolt_constants import CTX_REVOLT_CHANNEL_ID, MAX_MSG_LEN


class RevoltSend(Tool):
    async def execute(
        self,
        channel_id: str = "",
        content: str = "",
        **kwargs,
    ):
        if not channel_id and self.agent and self.agent.context:
            channel_id = self.agent.context.data.get(CTX_REVOLT_CHANNEL_ID, "") or ""

        if not channel_id:
            return Response(
                message=(
                    "Error: channel_id is required and no bridged channel is set "
                    "on this context."
                ),
                break_loop=False,
            )
        if not content:
            return Response(message="Error: content is required.", break_loop=False)

        from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
        from usr.plugins.parley.helpers import revolt_sent_ids as sent_ids

        platform = get_platform()
        chunks = split_message(content, MAX_MSG_LEN)
        sent = 0
        try:
            for chunk in chunks:
                sent_ids.mark_pending(channel_id, chunk)
                result = await platform.send_message(channel_id, chunk)
                if isinstance(result, dict) and "_id" in result:
                    sent_ids.record(result["_id"])
                sent += 1
        except Exception as e:
            return Response(
                message=f"Revolt API error after {sent}/{len(chunks)} chunk(s): {e}",
                break_loop=False,
            )

        if self.agent and self.agent.context:
            self.agent.context.data["revolt_send_used"] = True

        parts = f"{sent} part(s)" if len(chunks) > 1 else "message"
        return Response(
            message=f"Sent {parts} to channel {channel_id}.",
            break_loop=True,
        )

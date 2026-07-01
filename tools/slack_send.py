"""slack_send — send a message to a Slack channel."""

from __future__ import annotations

from helpers.tool import Tool, Response
from usr.plugins.parley.helpers.slack_constants import CTX_SLACK_CHANNEL_ID, SLACK_MAX_MSG_LEN


class SlackSend(Tool):
    async def execute(
        self,
        channel_id: str = "",
        content: str = "",
        **kwargs,
    ) -> Response:
        if not channel_id:
            channel_id = self.agent.context.data.get(CTX_SLACK_CHANNEL_ID, "") or ""

        if not channel_id:
            return Response(
                message="Error: channel_id is required and no bridged Slack channel is set.",
                break_loop=False,
            )
        if not content:
            return Response(message="Error: content is required.", break_loop=False)

        try:
            from usr.plugins.parley.infrastructure.slack.slack_platform import get_platform
            from usr.plugins.parley.core.message_split import split_message

            platform = get_platform()
            chunks = split_message(content, SLACK_MAX_MSG_LEN)
            sent = 0
            for chunk in chunks:
                await platform.send_message(channel_id, chunk)
                sent += 1
            self.agent.context.data["slack_send_used"] = True
        except Exception as e:
            return Response(
                message=f"Slack API error after {sent}/{len(chunks)} chunk(s): {e}",
                break_loop=False,
            )

        parts = f"{len(chunks)} part(s)" if len(chunks) > 1 else "message"
        return Response(
            message=f"Sent {parts} to Slack channel {channel_id}.",
            break_loop=False,
        )

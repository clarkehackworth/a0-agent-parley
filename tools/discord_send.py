"""discord_send — send a message to a Discord channel."""

from __future__ import annotations

from helpers.tool import Tool, Response
from usr.plugins.parley.helpers.discord_constants import CTX_DISCORD_CHANNEL_ID, DISCORD_MAX_MSG_LEN


class DiscordSend(Tool):
    async def execute(
        self,
        channel_id: str = "",
        content: str = "",
        **kwargs,
    ) -> Response:
        if not channel_id:
            channel_id = self.agent.context.data.get(CTX_DISCORD_CHANNEL_ID, "") or ""

        if not channel_id:
            return Response(
                message="Error: channel_id is required and no bridged Discord channel is set.",
                break_loop=False,
            )
        if not content:
            return Response(message="Error: content is required.", break_loop=False)

        try:
            from usr.plugins.parley.infrastructure.discord.discord_platform import get_platform
            from usr.plugins.parley.core.message_split import split_message

            platform = get_platform()
            chunks = split_message(content, DISCORD_MAX_MSG_LEN)
            sent = 0
            for chunk in chunks:
                await platform.send_message(channel_id, chunk)
                sent += 1
            self.agent.context.data["discord_send_used"] = True
        except Exception as e:
            return Response(
                message=f"Discord API error after {sent}/{len(chunks)} chunk(s): {e}",
                break_loop=False,
            )

        parts = f"{len(chunks)} part(s)" if len(chunks) > 1 else "message"
        return Response(
            message=f"Sent {parts} to Discord channel {channel_id}.",
            break_loop=False,
        )

"""revolt_channels — list channels in the configured Revolt server."""

from __future__ import annotations

from helpers.tool import Tool, Response


class RevoltChannels(Tool):
    async def execute(self, **kwargs):
        from usr.plugins.parley.infrastructure.revolt.revolt_config import load_revolt_config
        from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform

        try:
            cfg = load_revolt_config()
            server_id = cfg.get("server_id", "")
            if not server_id:
                return Response(message="Error: server_id not set in revolt plugin config.", break_loop=False)

            server, channels = await get_platform().list_server_channels(server_id)
        except Exception as e:
            return Response(message=f"Revolt API error: {e}", break_loop=False)

        server_name = server.get("name", server_id)
        lines = [f"Server: {server_name}", f"Channels ({len(channels)}):"]
        for ch in channels:
            lines.append(f"  #{ch.name}  [{ch.channel_type}]  id={ch.id}")

        return Response(message="\n".join(lines), break_loop=False)

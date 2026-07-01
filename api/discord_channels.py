"""GET /api/plugins/parley/discord_channels — list Discord guild channels."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class DiscordChannelsApi(ApiHandler):

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST", "GET"]

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    async def process(self, input: Input, request: Request) -> Output:
        try:
            from usr.plugins.parley.infrastructure.discord.discord_config import load_discord_config
            from usr.plugins.parley.infrastructure.discord.discord_platform import get_platform

            cfg = load_discord_config()
            if not cfg.get("bot_token"):
                return jsonify({"ok": False, "not_configured": True, "error": "Discord bot token is not set."})

            guild_id = cfg.get("guild_id", "")
            platform = get_platform()
            bot = await platform.get_bot()
            server, channels = await platform.list_server_channels(guild_id)

            return jsonify({
                "ok": True,
                "server_name": server.get("name", guild_id),
                "server_id": guild_id,
                "bot_user_id": bot.get("id", ""),
                "watched_channels": cfg.get("watched_channels", []),
                "channels": [
                    {"id": ch.id, "name": ch.name, "type": ch.channel_type}
                    for ch in channels
                ],
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

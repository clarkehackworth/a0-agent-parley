"""GET /api/plugins/parley/channels — return channel list for the sidebar."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class RevoltChannelsApi(ApiHandler):

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
            from usr.plugins.parley.infrastructure.revolt.revolt_config import load_revolt_config
            from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform

            cfg = load_revolt_config()
            if not cfg.get("bot_token"):
                return jsonify({"ok": False, "not_configured": True, "error": "Revolt bot token is not set."})
            server_id = cfg.get("server_id", "")

            server, channels = await get_platform().list_server_channels(server_id)

            return jsonify({
                "ok": True,
                "server_name": server.get("name", server_id),
                "server_id": server_id,
                "watched_channels": cfg.get("watched_channels", []),
                "channels": [
                    {"id": ch.id, "name": ch.name, "type": ch.channel_type}
                    for ch in channels
                    if ch.channel_type in ("TextChannel", "VoiceChannel", "SavedMessages")
                ],
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e), "channels": []})

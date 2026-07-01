"""GET /api/plugins/parley/slack_channels — list Slack workspace channels."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class SlackChannelsApi(ApiHandler):

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
            from usr.plugins.parley.infrastructure.slack.slack_config import load_slack_config
            from usr.plugins.parley.infrastructure.slack.slack_platform import get_platform

            cfg = load_slack_config()
            if not cfg.get("bot_token"):
                return jsonify({"ok": False, "not_configured": True, "error": "Slack bot token is not set."})

            platform = get_platform()
            bot_info = await platform.get_bot()
            server, channels = await platform.list_server_channels(cfg.get("team_id", ""))

            return jsonify({
                "ok": True,
                "server_name": server.get("name", "Slack Workspace"),
                "server_id": server.get("id", ""),
                "bot_user_id": bot_info.get("user_id", ""),
                "watched_channels": cfg.get("watched_channels", []),
                "channels": [
                    {"id": ch.id, "name": ch.name, "type": ch.channel_type}
                    for ch in channels
                ],
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

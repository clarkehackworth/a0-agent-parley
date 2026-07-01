"""POST /api/plugins/parley/slack_update_channels — save slack.watched_channels."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class SlackUpdateChannelsApi(ApiHandler):

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    async def process(self, input: Input, request: Request) -> Output:
        try:
            from helpers import plugins as a0_plugins

            watched = input.get("watched_channels", [])
            if not isinstance(watched, list):
                return jsonify({"ok": False, "error": "watched_channels must be a list"})

            full_cfg = a0_plugins.get_plugin_config("parley") or {}
            slack_cfg = dict(full_cfg.get("slack") or {})
            slack_cfg["watched_channels"] = watched
            full_cfg["slack"] = slack_cfg

            a0_plugins.save_plugin_config("parley", "", "", full_cfg)

            from usr.plugins.parley.helpers.slack_listener import request_reconnect, is_listener_running, start_listener
            if is_listener_running():
                request_reconnect()
            else:
                start_listener(agent=None)

            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

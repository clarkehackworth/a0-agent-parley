"""POST /api/plugins/parley/update_channels — save watched_channels config."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class RevoltUpdateChannelsApi(ApiHandler):

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
            from usr.plugins.parley.infrastructure.revolt.revolt_config import load_revolt_config
            from helpers import plugins as a0_plugins

            watched = input.get("watched_channels", [])
            if not isinstance(watched, list):
                return jsonify({"ok": False, "error": "watched_channels must be a list"})

            cfg = load_revolt_config()
            cfg["watched_channels"] = watched

            a0_plugins.save_plugin_config("parley", "", "", cfg)

            from usr.plugins.parley.helpers.revolt_listener import request_reconnect, is_listener_running, start_listener
            if is_listener_running():
                request_reconnect()
            else:
                start_listener(agent=None)

            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

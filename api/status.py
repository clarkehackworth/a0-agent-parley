"""POST /api/plugins/parley/status — return connection status."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class RevoltStatusApi(ApiHandler):

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
            from usr.plugins.parley.infrastructure.revolt.revolt_config import (
                load_revolt_config, get_token,
            )

            cfg = load_revolt_config()
            token = get_token(cfg)

            return jsonify({
                "ok": True,
                "connected": bool(token),
                "server_id": cfg.get("server_id", ""),
                "url": cfg.get("url", ""),
            })
        except Exception as e:
            return jsonify({"ok": False, "connected": False, "error": str(e)})

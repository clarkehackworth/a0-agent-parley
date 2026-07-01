"""POST /api/plugins/parley/whoami — return the authenticated Revolt user's ID."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class RevoltWhoamiApi(ApiHandler):

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
            from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
            data = await get_platform().get_bot()
            return jsonify({
                "ok": True,
                "user_id": data.get("_id", ""),
                "username": data.get("username", ""),
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

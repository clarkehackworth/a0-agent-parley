"""POST /api/plugins/parley/bridge_message  — DEPRECATED.

Incoming Revolt messages are now ingested solely by the WebSocket listener
(helpers/revolt_listener.py), which responds to @mentions only and runs the
agent in a hidden background context. This HTTP endpoint used to create a
visible per-channel chat and respond to any content, which double-processed
messages (the webui panel polled and forwarded here while the listener also
ran) and contradicted the @mention-only / background design.

The route is kept as an explicit no-op so any stale caller fails loudly
instead of silently spawning a second response.
"""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class RevoltBridgeMessageApi(ApiHandler):

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
        return jsonify({
            "ok": False,
            "error": (
                "bridge_message is deprecated. Revolt messages are handled by the "
                "WebSocket listener (@mentions only)."
            ),
        })

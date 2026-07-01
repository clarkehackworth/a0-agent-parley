"""POST /api/plugins/parley/slack_send_message — send a message to a Slack channel."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class SlackSendMessageApi(ApiHandler):

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
        channel_id = input.get("channel_id", "")
        content = input.get("content", "").strip()

        if not channel_id:
            return jsonify({"ok": False, "error": "channel_id is required"})
        if not content:
            return jsonify({"ok": False, "error": "content is required"})

        try:
            from usr.plugins.parley.infrastructure.slack.slack_platform import get_platform
            from usr.plugins.parley.core.message_split import split_message
            from usr.plugins.parley.helpers.slack_constants import SLACK_MAX_MSG_LEN

            platform = get_platform()
            chunks = split_message(content, SLACK_MAX_MSG_LEN)
            for chunk in chunks:
                await platform.send_message(channel_id, chunk)

            return jsonify({"ok": True, "chunks": len(chunks)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

"""POST /api/plugins/parley/discord_messages — fetch recent messages from a Discord channel."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class DiscordMessagesApi(ApiHandler):

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
        recent_limit = int(input.get("recent_limit", 50))
        before = input.get("before")

        if not channel_id:
            return jsonify({"ok": False, "error": "channel_id is required"})

        try:
            from usr.plugins.parley.infrastructure.discord.discord_platform import get_platform

            platform = get_platform()
            # ponytail: no context-window backfill; just recent messages
            messages, user_map = await platform.fetch_messages(
                channel_id, limit=recent_limit, before=before
            )

            return jsonify({
                "ok": True,
                "channel_id": channel_id,
                "keywords": [],
                "backfill_ids": [],
                "messages": [
                    {
                        "id": m.id,
                        "author_id": m.author_id,
                        "author": user_map.get(m.author_id, m.author_id[:8] if m.author_id else "?"),
                        "content": m.content,
                        "attachments_count": m.attachments_count,
                        "formatted": f"[{user_map.get(m.author_id, '?')}] {m.content}",
                    }
                    for m in messages
                ],
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

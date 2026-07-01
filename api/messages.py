"""POST /api/plugins/parley/messages — fetch context-aware messages for a channel."""

from __future__ import annotations

from flask import jsonify
from helpers.api import ApiHandler, Input, Output, Request


class RevoltMessagesApi(ApiHandler):

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
        search_limit = int(input.get("search_limit", 15))
        search_terms = input.get("search_terms")

        if not channel_id:
            return jsonify({"ok": False, "error": "channel_id is required"})

        try:
            from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
            from usr.plugins.parley.core.context_config import ContextWindowConfig
            from usr.plugins.parley.core.context_window import build_context_window
            from usr.plugins.parley.core.formatting import format_message

            terms: list[str] | None = None
            if isinstance(search_terms, str) and search_terms.strip():
                terms = search_terms.split()
            elif isinstance(search_terms, list):
                terms = search_terms

            win_cfg = ContextWindowConfig(recent_limit=recent_limit, search_limit=search_limit)
            messages, user_map, keywords = await build_context_window(
                get_platform(),
                channel_id=channel_id,
                config=win_cfg,
                search_terms=terms,
            )

            return jsonify({
                "ok": True,
                "channel_id": channel_id,
                "keywords": keywords,
                "messages": [
                    {
                        "id": m.id,
                        "author_id": m.author_id,
                        "author": user_map.get(m.author_id, m.author_id[:8] if m.author_id else "?"),
                        "content": m.content,
                        "attachments": m.attachments_count,
                        "formatted": format_message(m, user_map=user_map),
                    }
                    for m in messages
                ],
            })
        except Exception as e:
            import traceback
            return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()})

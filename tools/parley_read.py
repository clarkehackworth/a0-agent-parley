"""parley_read — context-aware channel message retrieval."""

from __future__ import annotations

from helpers.tool import Tool, Response


class ParleyRead(Tool):
    async def execute(
        self,
        channel_id: str = "",
        recent_limit: int = 25,
        search_limit: int = 15,
        search_terms: str = "",
        **kwargs,
    ):
        if not channel_id:
            return Response(message="Error: channel_id is required.", break_loop=False)

        try:
            recent_limit = int(recent_limit)
            search_limit = int(search_limit)
        except (ValueError, TypeError):
            return Response(message="Error: recent_limit and search_limit must be integers.", break_loop=False)

        terms: list[str] | None = None
        if search_terms:
            terms = [t.strip() for t in search_terms.replace(",", " ").split() if t.strip()]

        from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
        from usr.plugins.parley.core.context_config import ContextWindowConfig
        from usr.plugins.parley.core.context_window import build_context_window
        from usr.plugins.parley.core.formatting import format_message

        try:
            win_cfg = ContextWindowConfig(recent_limit=recent_limit, search_limit=search_limit)
            messages, user_map, keywords = await build_context_window(
                get_platform(),
                channel_id=channel_id,
                config=win_cfg,
                search_terms=terms,
            )
        except Exception as e:
            return Response(message=f"Revolt API error: {e}", break_loop=False)

        if not messages:
            return Response(message="No messages found in this channel.", break_loop=False)

        lines = [f"Channel {channel_id} — {len(messages)} messages"]
        if keywords:
            lines.append(f"Context keywords used for backfill: {', '.join(keywords)}")
        lines.append("")

        for msg in messages:
            lines.append(format_message(msg, user_map=user_map))

        return Response(message="\n".join(lines), break_loop=False)

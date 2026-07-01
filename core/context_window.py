"""Platform-agnostic context window builder.

Depends on the ChatPlatform port — knows nothing about Revolt or Agent Zero.
Operates on typed Message models; raw dicts never cross into this layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from usr.plugins.parley.ports.chat_platform import ChatPlatform
    from usr.plugins.parley.core.context_config import ContextWindowConfig
    from usr.plugins.parley.core.models import Message


def _import_formatting():
    try:
        from usr.plugins.parley.core.formatting import ulid_to_timestamp
    except ImportError:
        from core.formatting import ulid_to_timestamp  # type: ignore[no-redef]
    return ulid_to_timestamp


def _import_keywords():
    try:
        from usr.plugins.parley.core.keywords import extract_keywords
    except ImportError:
        from core.keywords import extract_keywords  # type: ignore[no-redef]
    return extract_keywords


def _within_age(msg: "Message", max_age_days: float) -> bool:
    if not max_age_days:
        return True
    try:
        ulid_to_timestamp = _import_formatting()
        age = datetime.now(timezone.utc) - ulid_to_timestamp(msg.id)
        return age.total_seconds() <= max_age_days * 86400
    except Exception:
        return True


def _is_bot_status_msg(msg: "Message", bot_id: str) -> bool:
    if not bot_id or msg.author_id != bot_id:
        return False
    first_line = (msg.content or "").split("\n", 1)[0]
    return first_line.startswith(("⚙️ Working on it", "✅ Done"))


def _filter_msgs(msgs: "list[Message]", bot_id: str, max_age_days: float) -> "list[Message]":
    return [m for m in msgs if not _is_bot_status_msg(m, bot_id) and _within_age(m, max_age_days)]


async def _expand_neighbors(
    platform: "ChatPlatform", channel_id: str, hits: "list[Message]", neighbors: int
) -> "tuple[list[list[Message]], dict[str, str]]":
    span = neighbors * 2 + 1
    groups: list[list] = []
    users: dict[str, str] = {}
    for hit in hits:
        if not hit.id:
            groups.append([])
            continue
        try:
            msgs, umap = await platform.fetch_messages(channel_id, limit=span, nearby=hit.id)
            users = {**umap, **users}
        except Exception:
            msgs = []
        groups.append(msgs)
    return groups, users


def _select_backfill(
    hits: "list[Message]", neighbor_groups: "list[list[Message]]", max_backfill: int
) -> "list[Message]":
    """Pick backfill messages preserving relevance order; most-relevant hits survive the cap."""
    ranked: list[tuple[int, object]] = [(rank, hit) for rank, hit in enumerate(hits)]
    for rank, group in enumerate(neighbor_groups):
        ranked.extend((rank, m) for m in group)
    ranked.sort(key=lambda rm: rm[0])

    chosen: list[Message] = []
    seen: set[str] = set()
    for _rank, msg in ranked:
        if not msg.id or msg.id in seen:
            continue
        seen.add(msg.id)
        chosen.append(msg)
        if len(chosen) >= max_backfill:
            break
    return chosen


_DEFAULT_CONFIG = None


def _default_config() -> "ContextWindowConfig":
    global _DEFAULT_CONFIG
    if _DEFAULT_CONFIG is None:
        try:
            from usr.plugins.parley.core.context_config import ContextWindowConfig
        except ImportError:
            from core.context_config import ContextWindowConfig  # type: ignore[no-redef]
        _DEFAULT_CONFIG = ContextWindowConfig()
    return _DEFAULT_CONFIG


async def build_context_window(
    platform: "ChatPlatform",
    channel_id: str,
    config: "ContextWindowConfig | None" = None,
    search_terms: list[str] | None = None,
    bot_id: str = "",
) -> "tuple[list[Message], dict[str, str], list[str]]":
    """
    Two-pass context builder:
      1. Fetch the `config.recent_limit` newest messages (anchor window).
      2. Optionally prepend the channel's first message and pinned messages.
      3. Search back through history for relevant context, expanding hits with
         their neighbours and capping the pool by relevance.
    Returns (merged_messages_sorted_oldest_first, user_map, keywords_used).
    """
    cfg = config if config is not None else _default_config()

    recent, user_map = await platform.fetch_messages(channel_id, limit=cfg.recent_limit)

    extract_keywords = _import_keywords()
    keywords = search_terms if search_terms is not None else extract_keywords(
        recent, min_length=cfg.min_keyword_length
    )

    backfill: list[Message] = []
    if keywords:
        query = " ".join(keywords[:4])
        hits, hit_users = await platform.search_messages(channel_id, query, limit=cfg.search_limit)
        if not hits:
            hits, hit_users = await platform.search_messages(channel_id, keywords[0], limit=cfg.search_limit)
        user_map = {**hit_users, **user_map}

        hits = _filter_msgs(hits, bot_id, cfg.max_age_days)

        neighbor_groups: list[list[Message]] = []
        if cfg.neighbors and hits:
            neighbor_groups, nbr_users = await _expand_neighbors(
                platform, channel_id, hits[:cfg.expand_top], cfg.neighbors
            )
            neighbor_groups = [_filter_msgs(g, bot_id, cfg.max_age_days) for g in neighbor_groups]  # ponytail: bot_id used only to strip status msgs now
            user_map = {**nbr_users, **user_map}

        backfill = _select_backfill(hits, neighbor_groups, max_backfill=cfg.search_limit)

    anchors: list[Message] = []
    if cfg.include_first:
        try:
            first_msgs, first_users = await platform.fetch_first_message(channel_id)
            user_map = {**first_users, **user_map}
            anchors.extend(first_msgs)
        except Exception:
            pass
    if cfg.include_pinned:
        try:
            pinned_msgs, pin_users = await platform.fetch_pinned_messages(channel_id)
            user_map = {**pin_users, **user_map}
            anchors.extend(pinned_msgs)
        except Exception:
            pass

    seen: set[str] = set()
    merged: list[Message] = []
    for msg in anchors + recent + backfill:
        if msg.id and msg.id not in seen:
            seen.add(msg.id)
            merged.append(msg)

    merged.sort(key=lambda m: m.id)
    return merged, user_map, keywords


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.models import Message

    def _m(id): return Message(id=id, author_id="u", content="")

    _hits = [_m("a"), _m("b"), _m("c")]
    _groups = [[_m("a"), _m("x")], [_m("y")]]
    assert [m.id for m in _select_backfill(_hits, _groups, 10)] == ["a", "x", "b", "y", "c"]
    assert [m.id for m in _select_backfill(_hits, _groups, 2)] == ["a", "x"]
    assert _select_backfill([], [], 5) == []
    print("ok context_window")

"""Platform-agnostic message formatting utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from usr.plugins.parley.core.models import Message


def ulid_to_timestamp(ulid: str) -> datetime:
    """Decode the timestamp embedded in a Revolt ULID message ID."""
    CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    ts_chars = ulid[:10].upper()
    ms = 0
    for ch in ts_chars:
        ms = ms * 32 + CROCKFORD.index(ch)
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def format_message(msg: "Message", user_map: dict[str, str] | None = None) -> str:
    """Format a Message as '[HH:MM DD-Mon] username: content'."""
    try:
        time_str = ulid_to_timestamp(msg.id).strftime("%H:%M %d-%b")
    except Exception:
        time_str = "??:??"

    username = (user_map or {}).get(msg.author_id) or (msg.author_id[:8] if msg.author_id else "unknown")

    content = msg.content
    if not content:
        content = f"[{msg.attachments_count} attachment(s)]" if msg.attachments_count else "[system message]"

    return f"[{time_str}] {username}: {content}"

"""Domain models — platform-agnostic data structures for messages, users, and channels.

Messages still flow as dicts through the codebase; these types establish the
canonical field names and serve as the target for future typed migration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    id: str
    author_id: str
    content: str
    attachments_count: int = 0
    ts: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            id=d.get("_id", ""),
            author_id=d.get("author", ""),
            content=(d.get("content") or "").strip(),
            attachments_count=len(d.get("attachments") or []),
        )


@dataclass
class User:
    id: str
    username: str

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        return cls(id=d.get("_id", ""), username=d.get("username", ""))


@dataclass
class Channel:
    id: str
    name: str
    channel_type: str = "TextChannel"

    @classmethod
    def from_dict(cls, d: dict) -> "Channel":
        return cls(
            id=d.get("_id", ""),
            name=d.get("name", ""),
            channel_type=d.get("channel_type", "TextChannel"),
        )


if __name__ == "__main__":
    m = Message.from_dict({"_id": "abc", "author": "u1", "content": "hello"})
    assert m.id == "abc" and m.content == "hello"
    u = User.from_dict({"_id": "u1", "username": "alice"})
    assert u.username == "alice"
    ch = Channel.from_dict({"_id": "c1", "name": "general", "channel_type": "TextChannel"})
    assert ch.channel_type == "TextChannel"
    print("ok models")

"""ChatPlatform — port (interface) for any chat backend.

Add a new platform by implementing this Protocol; no existing code changes.
"""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from usr.plugins.parley.core.models import Message, Channel


@runtime_checkable
class ChatPlatform(Protocol):
    async def send_message(self, channel_id: str, content: str) -> dict: ...
    async def send_reply(
        self, channel_id: str, content: str, reply_to_id: str, mention: bool = False
    ) -> dict: ...
    async def edit_message(self, channel_id: str, message_id: str, content: str) -> dict: ...
    async def fetch_messages(
        self,
        channel_id: str,
        limit: int = 25,
        before: str | None = None,
        nearby: str | None = None,
        sort: str = "Latest",
    ) -> tuple[list["Message"], dict[str, str]]: ...
    async def search_messages(
        self, channel_id: str, query: str, limit: int = 15
    ) -> tuple[list["Message"], dict[str, str]]: ...
    async def list_server_channels(
        self, server_id: str
    ) -> tuple[dict, list["Channel"]]: ...
    async def get_server(self, server_id: str) -> dict: ...
    async def fetch_first_message(
        self, channel_id: str
    ) -> tuple[list["Message"], dict[str, str]]: ...
    async def fetch_pinned_messages(
        self, channel_id: str
    ) -> tuple[list["Message"], dict[str, str]]: ...
    async def get_bot(self) -> dict: ...

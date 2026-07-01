"""DiscordPlatform — Discord REST API implementation of ChatPlatform port.

Uses discord.com/api/v10. Auth header: 'Authorization: Bot {token}'.
Message content intent must be enabled in the Discord developer portal
for the bot to receive message content via the gateway.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from usr.plugins.parley.infrastructure.discord.discord_config import load_discord_config, get_discord_token
from usr.plugins.parley.core.models import Message, Channel

_BASE = "https://discord.com/api/v10"

# Discord channel type integers
_TEXT_TYPES = {0, 5}   # GUILD_TEXT, GUILD_ANNOUNCEMENT
_VOICE_TYPES = {2}     # GUILD_VOICE
_TYPE_NAMES = {0: "TextChannel", 2: "VoiceChannel", 5: "TextChannel"}


def _msg(d: dict) -> Message:
    author = d.get("author") or {}
    return Message(
        id=d.get("id", ""),
        author_id=author.get("id", ""),
        content=(d.get("content") or "").strip(),
        attachments_count=len(d.get("attachments") or []),
    )


def _user_map(messages: list[dict]) -> dict[str, str]:
    return {
        (a := m.get("author") or {}).get("id", ""): a.get("username", "?")
        for m in messages
        if (m.get("author") or {}).get("id")
    }


def _ch(d: dict) -> Channel:
    ch_type = d.get("type", 0)
    return Channel(
        id=d.get("id", ""),
        name=d.get("name", ""),
        channel_type=_TYPE_NAMES.get(ch_type, "Other"),
    )


class DiscordPlatform:
    """Implements ChatPlatform for the Discord REST API."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        async with aiohttp.ClientSession() as session:
            resp = await session.request(method, f"{_BASE}/{path}", headers=self._headers, **kwargs)
            if resp.status == 401:
                raise RuntimeError("Discord: bot token rejected (401). Check the token in plugin config.")
            if resp.status == 403:
                raise RuntimeError(f"Discord: forbidden (403) on {method} /{path}. Check bot permissions.")
            if resp.status == 429:
                retry_after = (await resp.json()).get("retry_after", 1)
                raise RuntimeError(f"Discord: rate limited (429). Retry after {retry_after}s.")
            if resp.status == 204:
                return {}
            resp.raise_for_status()
            return await resp.json()

    async def send_message(self, channel_id: str, content: str) -> dict:
        return await self._request("POST", f"channels/{channel_id}/messages", json={"content": content})

    async def send_reply(
        self, channel_id: str, content: str, reply_to_id: str, mention: bool = False
    ) -> dict:
        return await self._request(
            "POST",
            f"channels/{channel_id}/messages",
            json={
                "content": content,
                "message_reference": {"message_id": reply_to_id},
                "allowed_mentions": {"replied_user": mention},
            },
        )

    async def edit_message(self, channel_id: str, message_id: str, content: str) -> dict:
        return await self._request(
            "PATCH", f"channels/{channel_id}/messages/{message_id}", json={"content": content}
        )

    async def fetch_messages(
        self,
        channel_id: str,
        limit: int = 25,
        before: str | None = None,
        nearby: str | None = None,
        sort: str = "Latest",
    ) -> tuple[list[Message], dict[str, str]]:
        params: dict = {"limit": min(limit, 100)}
        if nearby:
            params["around"] = nearby
        elif before:
            params["before"] = before
        # ponytail: Discord returns newest-first; sort param is not supported
        data: list[dict] = await self._request("GET", f"channels/{channel_id}/messages", params=params)
        return [_msg(m) for m in data], _user_map(data)

    async def search_messages(
        self, channel_id: str, query: str, limit: int = 15
    ) -> tuple[list[Message], dict[str, str]]:
        # ponytail: Discord has no bot-accessible message search API; return empty
        return [], {}

    async def list_server_channels(self, server_id: str) -> tuple[dict, list[Channel]]:
        server = await self.get_server(server_id)
        raw_channels: list[dict] = await self._request("GET", f"guilds/{server_id}/channels")
        channels = [
            _ch(c) for c in raw_channels
            if c.get("type") in _TEXT_TYPES | _VOICE_TYPES
        ]
        return server, channels

    async def get_server(self, server_id: str) -> dict:
        return await self._request("GET", f"guilds/{server_id}")

    async def fetch_first_message(self, channel_id: str) -> tuple[list[Message], dict[str, str]]:
        # ponytail: get oldest by fetching with a minimal snowflake as 'after'
        data: list[dict] = await self._request(
            "GET", f"channels/{channel_id}/messages", params={"limit": 1, "after": "0"}
        )
        return [_msg(m) for m in data], _user_map(data)

    async def fetch_pinned_messages(self, channel_id: str) -> tuple[list[Message], dict[str, str]]:
        try:
            data: list[dict] = await self._request("GET", f"channels/{channel_id}/pins")
            return [_msg(m) for m in data], _user_map(data)
        except Exception:
            return [], {}

    async def send_dm(self, user_id: str, content: str) -> dict:
        """Open (or reuse) a DM channel with user_id and send a message."""
        ch = await self._request("POST", "users/@me/channels", json={"recipient_id": user_id})
        return await self.send_message(ch["id"], content)

    async def get_bot(self) -> dict:
        return await self._request("GET", "users/@me")


def get_platform() -> DiscordPlatform:
    cfg = load_discord_config()
    return DiscordPlatform(token=get_discord_token(cfg))


if __name__ == "__main__":
    assert _TYPE_NAMES[0] == "TextChannel"
    assert _TYPE_NAMES[2] == "VoiceChannel"
    m = _msg({"id": "1", "author": {"id": "u1", "username": "alice"}, "content": "hi"})
    assert m.id == "1" and m.author_id == "u1" and m.content == "hi"
    print("ok discord_platform")

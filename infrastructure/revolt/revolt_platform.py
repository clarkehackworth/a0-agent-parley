"""RevoltPlatform — Revolt HTTP implementation of the ChatPlatform port.

All Revolt-specific endpoint knowledge lives here. Swap this for
SlackPlatform / DiscordPlatform without touching core or interface code.

Raw HTTP dicts are converted to typed models at this boundary; nothing above
this layer handles bare dicts for messages or channels.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from usr.plugins.parley.infrastructure.revolt.revolt_config import load_revolt_config, get_token
from usr.plugins.parley.core.models import Message, Channel


def _parse_messages(data: Any) -> tuple[list[Message], dict[str, str]]:
    """Convert a Revolt messages response (list or {messages, users}) to typed models."""
    if isinstance(data, list):
        return [Message.from_dict(m) for m in data], {}
    raw_msgs = data.get("messages", [])
    users = data.get("users", [])
    user_map = {u["_id"]: u.get("username", u["_id"][:8]) for u in users if "_id" in u}
    return [Message.from_dict(m) for m in raw_msgs], user_map


class RevoltPlatform:
    """Implements ChatPlatform for the Revolt REST API."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._token = token

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        headers = {"x-bot-token": self._token}
        async with aiohttp.ClientSession() as session:
            resp = await session.request(
                method, f"{self._base}/api/{path}", headers=headers, **kwargs
            )
            if resp.status == 401:
                try:
                    body = await resp.json()
                    detail = body.get("description") or body.get("type") or str(body)
                except Exception:
                    detail = await resp.text()
                raise RuntimeError(
                    f"Parley: bot token rejected (401) on {method} /api/{path} — "
                    f"server says: {detail!r}. "
                    "Check the bot token in the Revolt plugin config."
                )
            if resp.status == 429:
                raise RuntimeError(
                    f"Parley: rate limited (429) on {method} /api/{path}. "
                    "Too many requests sent at once — this is a bug, please report it."
                )
            resp.raise_for_status()
            if resp.content_type == "application/json":
                return await resp.json()
            return await resp.text()

    async def send_message(self, channel_id: str, content: str) -> dict:
        return await self._request(
            "POST", f"channels/{channel_id}/messages", json={"content": content}
        )

    async def send_reply(
        self, channel_id: str, content: str, reply_to_id: str, mention: bool = False
    ) -> dict:
        return await self._request(
            "POST",
            f"channels/{channel_id}/messages",
            json={"content": content, "replies": [{"id": reply_to_id, "mention": mention}]},
        )

    async def edit_message(self, channel_id: str, message_id: str, content: str) -> dict:
        return await self._request(
            "PATCH",
            f"channels/{channel_id}/messages/{message_id}",
            json={"content": content},
        )

    async def fetch_messages(
        self,
        channel_id: str,
        limit: int = 25,
        before: str | None = None,
        nearby: str | None = None,
        sort: str = "Latest",
    ) -> tuple[list[Message], dict[str, str]]:
        params: dict = {"limit": min(limit, 100), "include_users": "true"}
        if nearby:
            params["nearby"] = nearby
        else:
            params["sort"] = sort
            if before:
                params["before"] = before
        data = await self._request("GET", f"channels/{channel_id}/messages", params=params)
        return _parse_messages(data)

    async def search_messages(
        self, channel_id: str, query: str, limit: int = 15
    ) -> tuple[list[Message], dict[str, str]]:
        try:
            data = await self._request(
                "POST",
                f"channels/{channel_id}/search",
                json={"query": query, "limit": limit, "sort": "Relevance", "include_users": True},
            )
            return _parse_messages(data)
        except Exception:
            return [], {}

    async def list_server_channels(self, server_id: str) -> tuple[dict, list[Channel]]:
        server = await self.get_server(server_id)
        channel_ids = server.get("channels", [])
        channels: list[Channel] = []
        for cid in channel_ids:
            try:
                ch = await self._request("GET", f"channels/{cid}")
                channels.append(Channel.from_dict(ch))
                await asyncio.sleep(0.05)  # 50 ms gap → max ~20 req/s
            except Exception:
                pass
        return server, channels

    async def get_server(self, server_id: str) -> dict:
        return await self._request("GET", f"servers/{server_id}")

    async def fetch_first_message(self, channel_id: str) -> tuple[list[Message], dict[str, str]]:
        return await self.fetch_messages(channel_id, limit=1, sort="Oldest")

    async def fetch_pinned_messages(self, channel_id: str) -> tuple[list[Message], dict[str, str]]:
        try:
            data = await self._request("GET", f"channels/{channel_id}/pins")
            return _parse_messages(data)
        except Exception:
            return [], {}

    async def send_dm(self, user_id: str, content: str) -> dict:
        """Open (or reuse) a DM channel with user_id and send a message."""
        ch = await self._request("GET", f"users/{user_id}/dm")
        return await self.send_message(ch["_id"], content)

    async def get_bot(self) -> dict:
        return await self._request("GET", "bots/@me")


def get_platform() -> RevoltPlatform:
    cfg = load_revolt_config()
    return RevoltPlatform(base_url=cfg.get("url", ""), token=get_token(cfg))

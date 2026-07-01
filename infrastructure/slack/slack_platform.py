"""SlackPlatform — Slack Web API implementation of ChatPlatform port.

Uses slack.com/api/. Auth: 'Authorization: Bearer {bot_token}'.
Bot token (xoxb-) required. App token (xapp-) is only needed for
the Socket Mode listener, not for the REST platform.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from usr.plugins.parley.infrastructure.slack.slack_config import load_slack_config, get_slack_bot_token
from usr.plugins.parley.core.models import Message, Channel

_BASE = "https://slack.com/api"

_SCOPE_HINTS: dict[str, str] = {
    "missing_scope": "Add the required scope to your Slack app (api.slack.com/apps → OAuth & Permissions → Bot Token Scopes) then reinstall the app.",
}
_METHOD_SCOPES: dict[str, str] = {
    "conversations.list": "channels:read (public), groups:read (private), im:read (DMs)",
    "conversations.history": "channels:history, groups:history, im:history",
    "conversations.replies": "channels:history, groups:history, im:history",
    "chat.postMessage": "chat:write",
    "users.info": "users:read",
    "search.messages": "search:read",
}


def _slack_error(method: str, data: dict) -> str:
    err = data.get("error", "unknown")
    msg = f"Slack {method} error: {err}"
    if err == "missing_scope":
        needed = _METHOD_SCOPES.get(method)
        scopes = f" (needs: {needed})" if needed else ""
        msg += f"{scopes} — {_SCOPE_HINTS['missing_scope']}"
    return msg


def _msg(d: dict) -> Message:
    return Message(
        id=d.get("ts", ""),
        author_id=d.get("user", "") or d.get("bot_id", ""),
        content=(d.get("text") or "").strip(),
        attachments_count=len(d.get("files") or []) + len(d.get("attachments") or []),
    )


class SlackPlatform:
    """Implements ChatPlatform for the Slack Web API."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _get(self, method: str, **params) -> Any:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                f"{_BASE}/{method}", headers=self._headers, params=params
            )
            data = await resp.json()
            if not data.get("ok"):
                raise RuntimeError(_slack_error(method, data))
            return data

    async def _post(self, method: str, **body) -> Any:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                f"{_BASE}/{method}", headers=self._headers, json=body
            )
            data = await resp.json()
            if not data.get("ok"):
                raise RuntimeError(_slack_error(method, data))
            return data

    async def send_message(self, channel_id: str, content: str) -> dict:
        return await self._post("chat.postMessage", channel=channel_id, text=content)

    async def send_reply(
        self, channel_id: str, content: str, reply_to_id: str, mention: bool = False
    ) -> dict:
        # ponytail: reply_to_id is the thread_ts in Slack; mention flag ignored (not a Slack concept)
        return await self._post(
            "chat.postMessage", channel=channel_id, text=content, thread_ts=reply_to_id
        )

    async def edit_message(self, channel_id: str, message_id: str, content: str) -> dict:
        # message_id is the ts value in Slack
        return await self._post("chat.update", channel=channel_id, ts=message_id, text=content)

    async def fetch_messages(
        self,
        channel_id: str,
        limit: int = 25,
        before: str | None = None,
        nearby: str | None = None,
        sort: str = "Latest",
    ) -> tuple[list[Message], dict[str, str]]:
        # ponytail: nearby/sort not supported by Slack history; before maps to latest
        params: dict = {"channel": channel_id, "limit": min(limit, 200)}
        if before:
            params["latest"] = before
        data = await self._get("conversations.history", **params)
        msgs = data.get("messages", [])
        user_map = await self._resolve_users({m.get("user", "") for m in msgs if m.get("user")})
        return [_msg(m) for m in msgs], user_map

    async def search_messages(
        self, channel_id: str, query: str, limit: int = 15
    ) -> tuple[list[Message], dict[str, str]]:
        # ponytail: search.messages requires search:read scope; return empty if unavailable
        try:
            data = await self._get("search.messages", query=query, count=limit)
            matches = data.get("messages", {}).get("matches", [])
            return [_msg(m) for m in matches], {}
        except Exception:
            return [], {}

    async def list_server_channels(self, server_id: str) -> tuple[dict, list[Channel]]:
        server = await self.get_server(server_id)
        data = await self._get(
            "conversations.list",
            types="public_channel,private_channel",
            exclude_archived="true",
            limit=200,
        )
        channels = [
            Channel(id=c["id"], name=c.get("name", ""), channel_type="TextChannel")
            for c in data.get("channels", [])
        ]
        return server, channels

    async def get_server(self, server_id: str) -> dict:
        # ponytail: server_id unused for Slack; team.info returns the workspace
        try:
            data = await self._get("team.info")
            team = data.get("team", {})
            return {"id": team.get("id", ""), "name": team.get("name", server_id)}
        except Exception:
            return {"id": server_id, "name": server_id}

    async def fetch_first_message(self, channel_id: str) -> tuple[list[Message], dict[str, str]]:
        data = await self._get("conversations.history", channel=channel_id, limit=1, oldest="0")
        msgs = data.get("messages", [])
        return [_msg(m) for m in msgs], {}

    async def fetch_pinned_messages(self, channel_id: str) -> tuple[list[Message], dict[str, str]]:
        try:
            data = await self._get("pins.list", channel=channel_id)
            items = data.get("items", [])
            msgs = [_msg(item["message"]) for item in items if "message" in item]
            return msgs, {}
        except Exception:
            return [], {}

    async def send_dm(self, user_id: str, content: str) -> dict:
        """Send a DM to user_id. Slack auto-opens the IM channel when posting to a user ID."""
        return await self.send_message(user_id, content)

    async def get_bot(self) -> dict:
        return await self._get("auth.test")

    async def _resolve_users(self, user_ids: set[str]) -> dict[str, str]:
        user_map: dict[str, str] = {}
        for uid in user_ids:
            if not uid:
                continue
            try:
                data = await self._get("users.info", user=uid)
                user = data.get("user", {})
                user_map[uid] = user.get("display_name") or user.get("real_name") or uid
            except Exception:
                user_map[uid] = uid
        return user_map


def get_platform() -> SlackPlatform:
    cfg = load_slack_config()
    return SlackPlatform(token=get_slack_bot_token(cfg))


if __name__ == "__main__":
    m = _msg({"ts": "123.456", "user": "U123", "text": "hello"})
    assert m.id == "123.456" and m.author_id == "U123" and m.content == "hello"
    print("ok slack_platform")

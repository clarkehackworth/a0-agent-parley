"""Persistent Revolt WebSocket listener for the chat bridge.

Connects to Revolt's event stream, filters messages by configured channels,
and routes them into Agent Zero's LLM — no browser required.

Singleton pattern mirrors the Telegram plugin's ChatBridgeBot:
  _listener_instance / _listener_thread / _listener_loop live at module
  level so reimports of this extension don't create duplicate listeners.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("revolt_listener")

_listener_instance: Optional["RevoltListener"] = None
_listener_thread: Optional[threading.Thread] = None
_listener_loop: Optional[asyncio.AbstractEventLoop] = None
_auto_start_attempted: bool = False
_active_ws = None  # current websockets.WebSocketClientProtocol, if any

_seen_msg_ids: "collections.OrderedDict[str, float]" = collections.OrderedDict()
_seen_lock = threading.Lock()
_SEEN_MAX = 2000


def _already_seen(msg_id: str) -> bool:
    """Return True if this message id was already handled; otherwise record it."""
    if not msg_id:
        return False
    with _seen_lock:
        if msg_id in _seen_msg_ids:
            return True
        _seen_msg_ids[msg_id] = time.monotonic()
        while len(_seen_msg_ids) > _SEEN_MAX:
            _seen_msg_ids.popitem(last=False)
    return False


def is_listener_running() -> bool:
    return (
        _listener_thread is not None
        and _listener_thread.is_alive()
    )


def start_listener(agent) -> None:
    """Start the Revolt WebSocket listener on a dedicated background thread."""
    global _listener_instance, _listener_thread, _listener_loop

    if is_listener_running():
        return

    loop = asyncio.new_event_loop()
    _listener_loop = loop

    instance = RevoltListener(agent)
    _listener_instance = instance

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(instance.run())

    t = threading.Thread(target=_run, name="revolt-listener", daemon=True)
    _listener_thread = t
    t.start()
    logger.info("Revolt listener thread started.")


def request_reconnect() -> None:
    """Close the active WebSocket so the listener reconnects with fresh credentials."""
    ws = _active_ws
    loop = _listener_loop
    if ws is None or loop is None or not loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(ws.close(), loop)
    logger.info("Revolt listener reconnect requested (credentials changed).")


class RevoltListener:
    """WebSocket listener that bridges Revolt messages into Agent Zero."""

    BACKOFF_BASE = 2.0
    BACKOFF_MAX = 60.0

    def __init__(self, agent):
        self._agent = agent
        self._server_channel_ids: set[str] = set()
        self._watched: list[str] = []
        self._cfg: dict = {}

    async def run(self) -> None:
        """Reconnect loop — runs forever until the process exits."""
        attempt = 0
        while True:
            try:
                await self._connect_and_listen()
                attempt = 0
            except Exception as e:
                delay = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                logger.warning(
                    "Revolt listener disconnected (%s: %s). Reconnecting in %.0fs.",
                    type(e).__name__, e, delay,
                )
                await asyncio.sleep(delay)
                attempt += 1

    async def _connect_and_listen(self) -> None:
        import websockets
        from usr.plugins.parley.infrastructure.revolt.revolt_config import (
            load_revolt_config, get_token,
        )

        self._cfg = load_revolt_config()
        self._watched = self._cfg.get("watched_channels") or []

        ws_url = await self._make_ws_url(self._cfg["url"])
        token = get_token(self._cfg)

        logger.info("Revolt listener connecting to %s", ws_url)

        global _active_ws
        async with websockets.connect(ws_url) as ws:
            _active_ws = ws
            try:
                await ws.send(json.dumps({"type": "Authenticate", "token": token}))

                async for raw in ws:
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type", "")

                    if etype == "Ready":
                        await self._handle_ready(event)
                    elif etype == "ChannelCreate":
                        self._handle_channel_create(event)
                    elif etype == "Message":
                        await self._handle_message(event)
            finally:
                _active_ws = None

    async def _handle_ready(self, event: dict) -> None:
        server_id = self._cfg.get("server_id", "")
        servers = event.get("servers") or []
        for srv in servers:
            if srv.get("_id") == server_id:
                self._server_channel_ids = set(srv.get("channels") or [])
                break

        if not self._server_channel_ids and server_id:
            try:
                from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
                _, channels = await get_platform().list_server_channels(server_id)
                self._server_channel_ids = {c.id for c in channels}
            except Exception as e:
                logger.warning("Could not fetch server channels: %s", e)

        logger.info(
            "Revolt listener ready. server_channels=%d  watched=%s",
            len(self._server_channel_ids),
            self._watched or "(all)",
        )

    def _handle_channel_create(self, event: dict) -> None:
        server_id = self._cfg.get("server_id", "")
        if event.get("server") == server_id:
            ch_id = event.get("_id")
            if ch_id:
                self._server_channel_ids.add(ch_id)
                logger.info("New channel added to watch list: %s", ch_id)

    async def _handle_message(self, event: dict) -> None:
        channel_id = event.get("channel", "")
        author_id = event.get("author", "")
        content = (event.get("content") or "").strip()
        msg_id = event.get("_id", "")

        if not content:
            return

        bot_id = self._cfg.get("bot_id", "")
        if bot_id and author_id == bot_id:
            return

        from usr.plugins.parley.helpers import revolt_sent_ids as sent_ids
        if sent_ids.was_sent_by_us(msg_id, channel_id, content):
            return

        if self._server_channel_ids and channel_id not in self._server_channel_ids:
            # Not a server channel — check if it's a DM auth reply.
            from usr.plugins.parley.helpers.dm_auth import resolve_challenge
            if resolve_challenge("revolt", author_id, content):
                logger.debug("Revolt DM auth resolved for %s", author_id)
            return

        if self._watched and channel_id not in self._watched:
            return

        author = await self._resolve_username(author_id, channel_id)

        logger.info("Revolt message in %s from %s: %.80s", channel_id, author, content)

        if not (bot_id and f"<@{bot_id}>" in content):
            # Not a mention. If server_id wasn't configured so _server_channel_ids is
            # empty, DM replies fell through here — catch them by checking for a pending
            # challenge from this user (safe: only resolves if the password matches).
            if not self._server_channel_ids:
                from usr.plugins.parley.helpers.dm_auth import resolve_challenge
                if resolve_challenge("revolt", author_id, content):
                    logger.debug("Revolt DM auth resolved for %s (no server filter)", author_id)
            return

        if _already_seen(msg_id):
            logger.debug("Skipping already-handled Revolt message %s", msg_id)
            return

        asyncio.create_task(self._forward_mention(channel_id, author_id, author, content, msg_id))

    async def _forward_mention(
        self, channel_id: str, author_id: str, author: str, content: str, msg_id: str
    ) -> None:
        try:
            from usr.plugins.parley.interface.agent_zero.mention_handler import handle_mention
            await handle_mention(channel_id, author_id, author, content, msg_id)
        except Exception as e:
            logger.error("Failed to handle Revolt @mention: %s", e)

    async def _make_ws_url(self, http_url: str) -> str:
        import aiohttp
        base = http_url.rstrip("/")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base}/api") as resp:
                    data = await resp.json()
                    ws = data.get("ws", "")
                    if ws:
                        return ws
        except Exception:
            pass
        url = base
        if url.startswith("https://"):
            url = "wss://" + url[len("https://"):]
        elif url.startswith("http://"):
            url = "ws://" + url[len("http://"):]
        return f"{url}/ws"

    async def _resolve_username(self, user_id: str, channel_id: str) -> str:
        try:
            from usr.plugins.parley.infrastructure.revolt.revolt_platform import get_platform
            _msgs, user_map = await get_platform().fetch_messages(channel_id, limit=1)
            if user_id in user_map:
                return user_map[user_id]
        except Exception:
            pass
        return user_id[:8]

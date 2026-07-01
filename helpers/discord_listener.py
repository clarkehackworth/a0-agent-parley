"""Discord Gateway WebSocket listener.

Connects to the Discord Gateway, authenticates, and routes @mention
messages into Agent Zero as background contexts.

Requires MESSAGE_CONTENT intent to be enabled in the Discord developer
portal (Bot > Privileged Gateway Intents > Message Content Intent).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

logger = logging.getLogger("discord_listener")

# Discord Gateway v10
_GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

# Opcodes
_OP_DISPATCH = 0
_OP_HEARTBEAT = 1
_OP_IDENTIFY = 2
_OP_RECONNECT = 7
_OP_INVALID_SESSION = 9
_OP_HELLO = 10
_OP_HEARTBEAT_ACK = 11

# GUILD_MESSAGES (512) + MESSAGE_CONTENT (32768, privileged) + DIRECT_MESSAGES (4096)
_INTENTS = 512 + 32768 + 4096

_listener_instance: Optional["_DiscordListener"] = None
_listener_thread: Optional[threading.Thread] = None
_listener_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()
_reconnect_requested = False


class _DiscordListener:
    BACKOFF_BASE = 2.0
    BACKOFF_MAX = 60.0

    def __init__(self, agent) -> None:
        self._agent = agent
        self._cfg: dict = {}
        self._token: str = ""
        self._bot_id: str = ""
        self._sequence: Optional[int] = None
        self._heartbeat_interval: float = 41.25
        self._watched_channels: set[str] = set()

    async def run(self) -> None:
        attempt = 0
        while True:
            try:
                await self._connect()
                attempt = 0
            except Exception as e:
                delay = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                logger.warning("Discord listener disconnected (%s). Reconnecting in %.0fs.", e, delay)
                await asyncio.sleep(delay)
                attempt += 1

    async def _connect(self) -> None:
        import websockets
        from usr.plugins.parley.infrastructure.discord.discord_config import (
            load_discord_config, get_discord_token,
        )

        self._cfg = load_discord_config()
        self._token = get_discord_token(self._cfg)
        watched = self._cfg.get("watched_channels", [])
        self._watched_channels = set(watched) if isinstance(watched, list) else set()

        async with websockets.connect(_GATEWAY_URL) as ws:
            heartbeat_task: Optional[asyncio.Task] = None
            async for raw in ws:
                global _reconnect_requested
                if _reconnect_requested:
                    _reconnect_requested = False
                    raise RuntimeError("reconnect requested by config change")

                payload = json.loads(raw)
                op = payload.get("op")

                if op == _OP_HELLO:
                    self._heartbeat_interval = payload["d"]["heartbeat_interval"] / 1000.0
                    if heartbeat_task:
                        heartbeat_task.cancel()
                    heartbeat_task = asyncio.create_task(self._heartbeat(ws))
                    await ws.send(json.dumps({
                        "op": _OP_IDENTIFY,
                        "d": {
                            "token": f"Bot {self._token}",
                            "intents": _INTENTS,
                            "properties": {
                                "os": "linux",
                                "browser": "agent-zero",
                                "device": "agent-zero",
                            },
                        },
                    }))

                elif op == _OP_DISPATCH:
                    self._sequence = payload.get("s")
                    t = payload.get("t")
                    d = payload.get("d") or {}
                    if t == "READY":
                        self._bot_id = (d.get("user") or {}).get("id", "")
                        logger.warning("Discord listener ready, bot_id=%s", self._bot_id)
                    elif t == "MESSAGE_CREATE":
                        await self._handle_message(d)

                elif op == _OP_HEARTBEAT:
                    await ws.send(json.dumps({"op": _OP_HEARTBEAT, "d": self._sequence}))

                elif op == _OP_RECONNECT:
                    if heartbeat_task:
                        heartbeat_task.cancel()
                    raise RuntimeError("Gateway requested reconnect")

                elif op == _OP_INVALID_SESSION:
                    if heartbeat_task:
                        heartbeat_task.cancel()
                    raise RuntimeError("Gateway: invalid session")

    async def _heartbeat(self, ws) -> None:
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                await ws.send(json.dumps({"op": _OP_HEARTBEAT, "d": self._sequence}))
        except asyncio.CancelledError:
            pass

    async def _handle_message(self, d: dict) -> None:
        author = d.get("author") or {}
        author_id = author.get("id", "")

        if author_id == self._bot_id or author.get("bot"):
            return

        # DMs have no guild_id — check for pending auth challenge before dropping.
        if not d.get("guild_id"):
            from usr.plugins.parley.helpers.dm_auth import resolve_challenge
            if resolve_challenge("discord", author_id, d.get("content", "")):
                logger.debug("Discord DM auth resolved for %s", author_id)
            return

        guild_id = d.get("guild_id", "")
        cfg_guild = self._cfg.get("guild_id", "")
        if cfg_guild and guild_id != cfg_guild:
            return

        channel_id = d.get("channel_id", "")
        if self._watched_channels and channel_id not in self._watched_channels:
            return

        content = d.get("content", "")
        if not self._bot_id:
            return
        if f"<@{self._bot_id}>" not in content and f"<@!{self._bot_id}>" not in content:
            return

        message_id = d.get("id", "")
        author_name = author.get("username", "unknown")
        logger.info("Discord @mention from %s in channel %s", author_name, channel_id)

        from usr.plugins.parley.interface.agent_zero.discord_mention_handler import handle_mention
        asyncio.create_task(handle_mention(channel_id, author_id, author_name, content, message_id))


def _run_listener(agent) -> None:
    global _listener_loop
    _listener_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_listener_loop)
    listener = _DiscordListener(agent)
    _listener_loop.run_until_complete(listener.run())


def is_listener_running() -> bool:
    return _listener_thread is not None and _listener_thread.is_alive()


def start_listener(agent=None) -> None:
    global _listener_instance, _listener_thread

    with _lock:
        if is_listener_running():
            return

        _listener_thread = threading.Thread(
            target=_run_listener, args=(agent,), daemon=True, name="discord-listener"
        )
        _listener_thread.start()
        logger.info("Discord listener thread started.")


def request_reconnect() -> None:
    global _reconnect_requested
    _reconnect_requested = True

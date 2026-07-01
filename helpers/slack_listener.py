"""Slack Socket Mode WebSocket listener.

Connects via Slack's Socket Mode using an app-level token (xapp-) and
routes @mention messages into Agent Zero as background contexts.

Requires: Socket Mode enabled in Slack app settings, and an Events API
subscription to the `message.channels` event (or `message.im` for DMs).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

import aiohttp

logger = logging.getLogger("slack_listener")

_CONNECTIONS_OPEN_URL = "https://slack.com/api/apps.connections.open"

_listener_thread: Optional[threading.Thread] = None
_listener_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()
_reconnect_requested = False


class _SlackListener:
    BACKOFF_BASE = 2.0
    BACKOFF_MAX = 60.0

    def __init__(self, agent) -> None:
        self._agent = agent
        self._cfg: dict = {}
        self._bot_token: str = ""
        self._app_token: str = ""
        self._bot_user_id: str = ""
        self._watched_channels: set[str] = set()

    async def run(self) -> None:
        attempt = 0
        while True:
            try:
                await self._connect()
                attempt = 0
            except asyncio.CancelledError:
                logger.warning("Slack listener: task cancelled — exiting.")
                return
            except Exception as e:
                delay = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                logger.warning("Slack listener disconnected (%s: %s). Reconnecting in %.0fs.",
                               type(e).__name__, e, delay)
                await asyncio.sleep(delay)
                attempt += 1

    async def _connect(self) -> None:
        import websockets
        from usr.plugins.parley.infrastructure.slack.slack_config import (
            load_slack_config, get_slack_bot_token, get_slack_app_token,
        )

        self._cfg = load_slack_config()
        self._bot_token = get_slack_bot_token(self._cfg)
        self._app_token = get_slack_app_token(self._cfg)
        watched = self._cfg.get("watched_channels", [])
        self._watched_channels = set(watched) if isinstance(watched, list) else set()

        if not self._bot_user_id:
            self._bot_user_id = await self._fetch_bot_user_id()
            logger.info("Slack listener: bot_user_id=%s", self._bot_user_id)

        wss_url = await self._open_connection()

        async with websockets.connect(wss_url) as ws:
            async for raw in ws:
                global _reconnect_requested
                if _reconnect_requested:
                    _reconnect_requested = False
                    raise RuntimeError("reconnect requested by config change")

                payload = json.loads(raw)
                msg_type = payload.get("type")

                if msg_type == "hello":
                    logger.warning("Slack Socket Mode connected (bot_user_id=%s, watched=%s).",
                                   self._bot_user_id, list(self._watched_channels) or "all")

                elif msg_type == "events_api":
                    envelope_id = payload.get("envelope_id")
                    if envelope_id:
                        await ws.send(json.dumps({"envelope_id": envelope_id}))

                    event = (payload.get("payload") or {}).get("event") or {}
                    logger.warning("Slack event: type=%s subtype=%s channel=%s channel_type=%s user=%s",
                                   event.get("type"), event.get("subtype"),
                                   event.get("channel"), event.get("channel_type"),
                                   event.get("user"))
                    if event.get("type") == "message":
                        await self._handle_message(event)

                elif msg_type == "disconnect":
                    raise RuntimeError("Slack Socket Mode requested disconnect")

    async def _fetch_bot_user_id(self) -> str:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {self._bot_token}"},
            )
            data = await resp.json()
            return data.get("user_id", "")

    async def _open_connection(self) -> str:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                _CONNECTIONS_OPEN_URL,
                headers={
                    "Authorization": f"Bearer {self._app_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            data = await resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack apps.connections.open failed: {data.get('error')}")
            return data["url"]

    async def _handle_message(self, event: dict) -> None:
        # Skip subtypes (edits, deletions, joins, etc.)
        if event.get("subtype"):
            return
        # Skip bot messages
        if event.get("bot_id"):
            return

        user_id = event.get("user", "")
        if user_id == self._bot_user_id:
            return

        channel_id = event.get("channel", "")
        channel_type = event.get("channel_type", "")
        is_dm = channel_type == "im"

        text = event.get("text", "")

        if is_dm:
            from usr.plugins.parley.helpers.dm_auth import resolve_challenge
            if resolve_challenge("slack", user_id, text):
                logger.debug("Slack DM auth resolved for %s", user_id)
                return
            # No pending challenge — fall through to handle_mention (normal DM handling).

        if not is_dm and self._watched_channels and channel_id not in self._watched_channels:
            logger.debug("Slack: dropped message in unwatched channel %s", channel_id)
            return

        if not is_dm and (not self._bot_user_id or f"<@{self._bot_user_id}>" not in text):
            logger.debug("Slack: dropped message in %s — no @mention (bot_user_id=%r)", channel_id, self._bot_user_id)
            return

        ts = event.get("ts", "")
        logger.info("Slack message from %s in %s (type=%s)", user_id, channel_id, channel_type)

        from usr.plugins.parley.interface.agent_zero.slack_mention_handler import handle_mention
        asyncio.create_task(handle_mention(channel_id, user_id, text, ts))


def _run_listener(agent) -> None:
    global _listener_loop
    try:
        _listener_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_listener_loop)
        listener = _SlackListener(agent)
        _listener_loop.run_until_complete(listener.run())
    except BaseException as e:
        logger.warning("Slack listener thread exited unexpectedly: %s: %s", type(e).__name__, e, exc_info=True)
    finally:
        logger.warning("Slack listener thread stopped.")


def is_listener_running() -> bool:
    # thread-name check survives module reloads that reset _listener_thread to None
    return any(t.name == "slack-listener" and t.is_alive() for t in threading.enumerate())


def start_listener(agent=None) -> None:
    global _listener_thread

    with _lock:
        if is_listener_running():
            return

        _listener_thread = threading.Thread(
            target=_run_listener, args=(agent,), daemon=True, name="slack-listener"
        )
        _listener_thread.start()
        logger.info("Slack listener thread started.")


def request_reconnect() -> None:
    global _reconnect_requested
    _reconnect_requested = True

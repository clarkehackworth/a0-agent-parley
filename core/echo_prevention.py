"""Echo prevention — tracks outbound messages to suppress our own WebSocket echoes.

Platform-agnostic: any chat adapter that sends messages should call mark_pending
before the HTTP POST and record after, then check was_sent_by_us in its listener.

Two-layer approach handles the race where the WS event arrives before the HTTP
response (and therefore before we have the message ID):

  Layer 1 — pre-send content reservation:
    mark_pending(channel_id, content) before HTTP POST.
    WS event always arrives after the server processes POST, so this is in time.

  Layer 2 — post-send ID confirmation:
    record(msg_id) once the response comes back.
    Catches content collisions (two users posting identical text simultaneously).
"""

import time
from collections import deque

_PENDING: dict[str, float] = {}
_PENDING_TTL = 15.0  # seconds

_SENT: deque[str] = deque(maxlen=500)


def mark_pending(channel_id: str, content: str) -> None:
    """Call BEFORE sending. Records (channel, content) so the listener can skip the echo."""
    key = _key(channel_id, content)
    _PENDING[key] = time.monotonic()
    _evict()


def record(message_id: str) -> None:
    """Call AFTER send returns the message ID."""
    _SENT.append(message_id)


def was_sent_by_us(message_id: str, channel_id: str = "", content: str = "") -> bool:
    """True if this message was sent by us (either layer matches)."""
    if message_id in _SENT:
        return True
    if channel_id and content:
        k = _key(channel_id, content)
        ts = _PENDING.get(k)
        if ts is not None and (time.monotonic() - ts) < _PENDING_TTL:
            _PENDING.pop(k, None)  # consume — one match per send
            return True
    return False


def _key(channel_id: str, content: str) -> str:
    return f"{channel_id}\x00{content}"


def _evict() -> None:
    cutoff = time.monotonic() - _PENDING_TTL
    stale = [k for k, t in _PENDING.items() if t < cutoff]
    for k in stale:
        del _PENDING[k]


if __name__ == "__main__":
    mark_pending("ch1", "hello")
    assert was_sent_by_us("", "ch1", "hello")
    assert not was_sent_by_us("", "ch1", "hello")  # consumed

    record("msg99")
    assert was_sent_by_us("msg99")
    assert was_sent_by_us("msg99")  # IDs are not consumed (deque)

    assert not was_sent_by_us("unknown", "ch1", "nope")
    print("ok echo_prevention")

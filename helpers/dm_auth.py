"""DM password challenge store for commands authorization.

When a user requests a command and a password is configured, the bot sends
a DM asking for the password. The listener resolves the challenge when the
user replies. Both the waiter and resolver run in the same asyncio event loop
(the listener loop), so asyncio.Event is safe here.
"""
import asyncio

_TIMEOUT = 120  # seconds to wait for DM reply

# platform → user_id → (password, event)
_pending: dict[str, dict[str, tuple[str, asyncio.Event]]] = {}


def create_challenge(platform: str, user_id: str, password: str) -> asyncio.Event:
    event = asyncio.Event()
    _pending.setdefault(platform, {})[user_id] = (password, event)
    return event


def resolve_challenge(platform: str, user_id: str, text: str) -> bool:
    """Set event and remove challenge if text contains the password. Returns True if resolved."""
    entry = _pending.get(platform, {}).get(user_id)
    if not entry:
        return False
    pw, event = entry
    if pw not in text:
        return False
    event.set()
    _pending[platform].pop(user_id, None)
    return True


def cancel_challenge(platform: str, user_id: str) -> None:
    _pending.get(platform, {}).pop(user_id, None)


async def wait_for_challenge(platform: str, user_id: str) -> bool:
    """Await the pending challenge. Returns True if resolved in time, False on timeout."""
    entry = _pending.get(platform, {}).get(user_id)
    if not entry:
        return False
    _, event = entry
    try:
        await asyncio.wait_for(event.wait(), timeout=_TIMEOUT)
        return True
    except asyncio.TimeoutError:
        cancel_challenge(platform, user_id)
        return False


if __name__ == "__main__":
    import asyncio as _asyncio

    async def _test():
        ev = create_challenge("revolt", "u1", "secret")
        assert not ev.is_set()
        assert not resolve_challenge("revolt", "u1", "wrong")
        assert resolve_challenge("revolt", "u1", "the secret is here")
        assert ev.is_set()
        assert not resolve_challenge("revolt", "u1", "secret")  # already removed

        ev2 = create_challenge("discord", "u2", "pw")
        cancel_challenge("discord", "u2")
        assert not ev2.is_set()
        print("ok dm_auth")

    _asyncio.run(_test())

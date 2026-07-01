"""Platform factory — returns the active ChatPlatform implementation.

Add a new platform here; everything else stays unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from usr.plugins.parley.ports.chat_platform import ChatPlatform

_REGISTRY: dict[str, str] = {
    "revolt":  "usr.plugins.parley.infrastructure.revolt.revolt_platform",
    "discord": "usr.plugins.parley.infrastructure.discord.discord_platform",
    "slack":   "usr.plugins.parley.infrastructure.slack.slack_platform",
}


def get_platform(provider: str = "revolt") -> "ChatPlatform":
    """Return a ChatPlatform instance for the given provider name."""
    module_path = _REGISTRY.get(provider)
    if not module_path:
        raise ValueError(
            f"Unknown chat platform: {provider!r}. "
            f"Available: {list(_REGISTRY)}"
        )
    import importlib
    module = importlib.import_module(module_path)
    return module.get_platform()

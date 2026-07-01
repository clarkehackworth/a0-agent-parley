"""Single source of truth for Discord plugin configuration.

Reads the `discord` subsection of the Revolt plugin config,
then overlays DISCORD_* environment variables.
"""

from __future__ import annotations

import os


def load_discord_config() -> dict:
    """Load the discord subsection from the plugin config."""
    cfg: dict = {}
    try:
        from helpers import plugins as a0_plugins
        full = a0_plugins.get_plugin_config("parley")
        if isinstance(full, dict):
            cfg = dict(full.get("discord") or {})
    except Exception:
        pass

    if not cfg:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "default_config.yaml")
        try:
            with open(config_path) as f:
                full = yaml.safe_load(f) or {}
            cfg = dict(full.get("discord") or {})
        except FileNotFoundError:
            cfg = {}

    watched = cfg.get("watched_channels", "")
    if isinstance(watched, str):
        cfg["watched_channels"] = [c.strip() for c in watched.split(",") if c.strip()]

    _bool = lambda v: v.lower() in ("1", "true", "yes")
    if token := os.environ.get("DISCORD_BOT_TOKEN"):
        cfg["bot_token"] = token
    if guild_id := os.environ.get("DISCORD_GUILD_ID"):
        cfg["guild_id"] = guild_id
    if bot_id := os.environ.get("DISCORD_BOT_ID"):
        cfg["bot_id"] = bot_id
    if auto_start := os.environ.get("DISCORD_AUTO_START"):
        cfg["auto_start"] = _bool(auto_start)
    if watched_env := os.environ.get("DISCORD_WATCHED_CHANNELS"):
        cfg["watched_channels"] = [c.strip() for c in watched_env.split(",") if c.strip()]

    return cfg


def get_discord_token(cfg: dict | None = None) -> str:
    if cfg is None:
        cfg = load_discord_config()
    token = cfg.get("bot_token", "")
    if not token:
        raise RuntimeError(
            "Discord: bot token is not configured. "
            "Open the plugin config and enter your Discord bot token."
        )
    return token

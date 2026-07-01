"""Single source of truth for Revolt plugin configuration.

All callers import load_revolt_config() from here instead of
duplicating _load_config() across helpers, tools, and extensions.
"""

from __future__ import annotations

import os


def load_revolt_config() -> dict:
    """Load plugin config from Agent Zero's config system, falling back to default_config.yaml."""
    cfg: dict = {}
    try:
        from helpers import plugins as a0_plugins
        result = a0_plugins.get_plugin_config("parley")
        if isinstance(result, dict):
            cfg = result
    except Exception:
        pass

    if not cfg:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "default_config.yaml")
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            cfg = {}

    watched = cfg.get("watched_channels", [])
    if isinstance(watched, str):
        cfg["watched_channels"] = [c.strip() for c in watched.split(",") if c.strip()]

    _bool = lambda v: v.lower() in ("1", "true", "yes")
    if url := os.environ.get("REVOLT_URL"):
        cfg["url"] = url
    if bot_token := os.environ.get("REVOLT_BOT_TOKEN"):
        cfg["bot_token"] = bot_token
    if bot_id := os.environ.get("REVOLT_BOT_ID"):
        cfg["bot_id"] = bot_id
    if server_id := os.environ.get("REVOLT_SERVER_ID"):
        cfg["server_id"] = server_id
    if auto_start := os.environ.get("REVOLT_AUTO_START"):
        cfg["auto_start"] = _bool(auto_start)
    if watched_env := os.environ.get("REVOLT_WATCHED_CHANNELS"):
        cfg["watched_channels"] = [c.strip() for c in watched_env.split(",") if c.strip()]
    if recent := os.environ.get("REVOLT_RECENT_LIMIT"):
        cfg["recent_limit"] = int(recent)
    if search := os.environ.get("REVOLT_SEARCH_LIMIT"):
        cfg["search_limit"] = int(search)
    if age := os.environ.get("REVOLT_MAX_AGE_DAYS"):
        cfg["max_age_days"] = float(age)
    if nbr := os.environ.get("REVOLT_NEIGHBORS"):
        cfg["neighbors"] = int(nbr)
    if top := os.environ.get("REVOLT_EXPAND_TOP"):
        cfg["expand_top"] = int(top)
    if first := os.environ.get("REVOLT_INCLUDE_FIRST"):
        cfg["include_first"] = _bool(first)
    if pinned := os.environ.get("REVOLT_INCLUDE_PINNED"):
        cfg["include_pinned"] = _bool(pinned)

    return cfg


def get_token(cfg: dict | None = None) -> str:
    """Return the bot token from config, raising if not set."""
    if cfg is None:
        cfg = load_revolt_config()
    token = cfg.get("bot_token", "")
    if not token:
        raise RuntimeError(
            "Parley: bot token is not configured. "
            "Open the Revolt plugin config and enter your bot token."
        )
    return token

"""Single source of truth for Slack plugin configuration.

Reads the `slack` subsection of the Revolt plugin config,
then overlays SLACK_* environment variables.
"""

from __future__ import annotations

import os


def load_slack_config() -> dict:
    """Load the slack subsection from the plugin config."""
    cfg: dict = {}
    try:
        from helpers import plugins as a0_plugins
        full = a0_plugins.get_plugin_config("parley")
        if isinstance(full, dict):
            cfg = dict(full.get("slack") or {})
    except Exception:
        pass

    if not cfg:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "default_config.yaml")
        try:
            with open(config_path) as f:
                full = yaml.safe_load(f) or {}
            cfg = dict(full.get("slack") or {})
        except FileNotFoundError:
            cfg = {}

    watched = cfg.get("watched_channels", "")
    if isinstance(watched, str):
        cfg["watched_channels"] = [c.strip() for c in watched.split(",") if c.strip()]

    _bool = lambda v: v.lower() in ("1", "true", "yes")
    if token := os.environ.get("SLACK_BOT_TOKEN"):
        cfg["bot_token"] = token
    if app_token := os.environ.get("SLACK_APP_TOKEN"):
        cfg["app_token"] = app_token
    if team_id := os.environ.get("SLACK_TEAM_ID"):
        cfg["team_id"] = team_id
    if auto_start := os.environ.get("SLACK_AUTO_START"):
        cfg["auto_start"] = _bool(auto_start)
    if watched_env := os.environ.get("SLACK_WATCHED_CHANNELS"):
        cfg["watched_channels"] = [c.strip() for c in watched_env.split(",") if c.strip()]

    return cfg


def get_slack_bot_token(cfg: dict | None = None) -> str:
    if cfg is None:
        cfg = load_slack_config()
    token = cfg.get("bot_token", "")
    if not token:
        raise RuntimeError(
            "Slack: bot token is not configured. "
            "Open the plugin config and enter your Slack bot token (xoxb-)."
        )
    return token


def get_slack_app_token(cfg: dict | None = None) -> str:
    if cfg is None:
        cfg = load_slack_config()
    token = cfg.get("app_token", "")
    if not token:
        raise RuntimeError(
            "Slack: app token is not configured. "
            "Open the plugin config and enter your Slack app token (xapp-) for Socket Mode."
        )
    return token

"""Agent Zero plugin hooks for the Revolt/Parley integration."""

from __future__ import annotations


def save_plugin_config(default=None, settings=None, **kwargs):
    """Reconnect all platform listeners when config is saved."""
    cfg = settings or default or {}

    try:
        from usr.plugins.parley.helpers import revolt_listener as rl
        if rl.is_listener_running():
            rl.request_reconnect()
    except Exception:
        pass

    try:
        from usr.plugins.parley.helpers import discord_listener as dl
        if dl.is_listener_running():
            dl.request_reconnect()
    except Exception:
        pass

    try:
        from usr.plugins.parley.helpers import slack_listener as sl
        if sl.is_listener_running():
            sl.request_reconnect()
    except Exception:
        pass

    return cfg

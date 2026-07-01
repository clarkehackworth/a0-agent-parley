"""Auto-start the Discord Gateway listener at Agent Zero startup.

Only starts if discord.auto_start: true and discord.bot_token is set.
Requires Message Content Intent enabled in the Discord developer portal.
"""

from __future__ import annotations

import logging

from helpers.extension import Extension

logger = logging.getLogger("discord_listener")

_start_attempted = False


class DiscordListenerStartup(Extension):

    def execute(self, **kwargs):
        global _start_attempted
        if _start_attempted:
            return
        _start_attempted = True

        try:
            from usr.plugins.parley.infrastructure.discord.discord_config import load_discord_config
            cfg = load_discord_config()

            if not cfg.get("auto_start", True):
                return
            if not cfg.get("bot_token"):
                return
            if not cfg.get("guild_id"):
                logger.warning("Discord listener: no guild_id configured, skipping.")
                return

            import usr.plugins.parley.helpers.discord_listener as dl
            if dl.is_listener_running():
                return

            logger.warning("Auto-starting Discord Gateway listener...")
            dl.start_listener(agent=None)
            logger.warning("Discord listener started in background thread.")

        except Exception as e:
            logger.warning(
                "Discord listener startup failed: %s: %s", type(e).__name__, e,
                exc_info=True,
            )

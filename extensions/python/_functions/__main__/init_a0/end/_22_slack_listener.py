"""Auto-start the Slack Socket Mode listener at Agent Zero startup.

Only starts if slack.auto_start: true, slack.bot_token and slack.app_token are set.
"""

from __future__ import annotations

import logging

from helpers.extension import Extension

logger = logging.getLogger("slack_listener")

_start_attempted = False


class SlackListenerStartup(Extension):

    def execute(self, **kwargs):
        global _start_attempted
        if _start_attempted:
            return
        _start_attempted = True

        try:
            from usr.plugins.parley.infrastructure.slack.slack_config import load_slack_config
            cfg = load_slack_config()

            if not cfg.get("auto_start", True):
                return
            if not cfg.get("bot_token"):
                return
            if not cfg.get("app_token"):
                logger.warning("Slack listener: no app_token (xapp-) configured, skipping.")
                return

            import importlib
            import usr.plugins.parley.helpers.slack_listener as sl
            importlib.reload(sl)  # always load from disk; is_listener_running uses thread names so reload is safe
            if sl.is_listener_running():
                return

            logger.warning("Auto-starting Slack Socket Mode listener...")
            sl.start_listener(agent=None)
            logger.warning("Slack listener started in background thread.")

        except Exception as e:
            logger.warning(
                "Slack listener startup failed: %s: %s", type(e).__name__, e,
                exc_info=True,
            )

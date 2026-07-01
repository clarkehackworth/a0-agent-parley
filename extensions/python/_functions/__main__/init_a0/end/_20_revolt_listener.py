"""Auto-start the Revolt WebSocket listener at Agent Zero startup.

Fires via the @extensible init_a0() hook in run_ui.py — guaranteed to run
once at Flask startup, with no browser or agent required.

Only starts if auto_start: true in default_config.yaml.
"""

from __future__ import annotations

import logging

from helpers.extension import Extension

logger = logging.getLogger("revolt_listener")

_start_attempted = False


class RevoltListenerStartup(Extension):

    def execute(self, **kwargs):
        global _start_attempted
        if _start_attempted:
            return
        _start_attempted = True

        try:
            from usr.plugins.parley.infrastructure.revolt.revolt_config import load_revolt_config
            cfg = load_revolt_config()

            if not cfg.get("auto_start", False):
                return

            if not cfg.get("server_id"):
                logger.warning("Revolt listener: no server_id configured, skipping.")
                return

            import usr.plugins.parley.helpers.revolt_listener as rl

            if rl.is_listener_running():
                return

            logger.warning("Auto-starting Revolt WebSocket listener...")
            rl.start_listener(agent=None)
            logger.warning("Revolt listener started in background thread.")

        except Exception as e:
            logger.warning(
                "Revolt listener startup failed: %s: %s", type(e).__name__, e,
                exc_info=True,
            )

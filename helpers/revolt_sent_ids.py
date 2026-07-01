"""Deprecated shim — logic moved to core/echo_prevention.py.

ponytail: kept so callers don't need to change import paths.
"""

from usr.plugins.parley.core.echo_prevention import mark_pending, record, was_sent_by_us

__all__ = ["mark_pending", "record", "was_sent_by_us"]

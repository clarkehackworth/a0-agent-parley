"""Shared context-data keys for the Revolt bridge.

Centralises constants duplicated across mention handler, extensions, and tools.
"""

CTX_REVOLT_CHANNEL_ID = "revolt_bridge_channel_id"
CTX_ORIGINAL_MSG_ID = "revolt_original_msg_id"
CTX_WORKING_MSG_ID = "revolt_working_msg_id"
CTX_WORKING_LINES = "revolt_working_lines"
CTX_SPINNER_TASK = "revolt_spinner_task"

MAX_MSG_LEN = 2000    # Revolt's hard per-message limit
MAX_MSG_BODY = 1900   # safe limit for editable messages (spinner headroom)

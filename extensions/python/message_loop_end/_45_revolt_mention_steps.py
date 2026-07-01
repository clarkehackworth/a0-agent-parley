"""Append per-iteration step updates by editing the "Working on it…" message."""

from __future__ import annotations

from helpers.extension import Extension
from agent import LoopData

from usr.plugins.parley.helpers.revolt_constants import CTX_WORKING_MSG_ID, CTX_WORKING_LINES, MAX_MSG_BODY

_MAX_STEP = 500


class RevoltMentionSteps(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        context = self.agent.context
        if not context.data.get(CTX_WORKING_MSG_ID):
            return

        line = _step_summary(loop_data)
        if not line:
            return

        # Accumulate lines on the context so we can build the full edited body.
        lines: list[str] = context.data.get(CTX_WORKING_LINES) or ["⚙️ Working on it…"]
        lines.append(line)

        # Trim from the top if we'd exceed Revolt's message limit, preserving
        # the header line and the most recent entries.
        body = "\n".join(lines)
        while len(body) > MAX_MSG_BODY and len(lines) > 2:
            lines.pop(1)  # drop oldest non-header line
            body = "\n".join(lines)

        context.data[CTX_WORKING_LINES] = lines


def _step_summary(loop_data: LoopData) -> str:
    parts: list[str] = []

    tool = loop_data.current_tool
    if tool:
        name = getattr(tool, "name", None) or str(tool)
        if name.startswith("revolt_"):
            return ""
        parts.append(f"🔧 `{name}`")

    response = (loop_data.last_response or "").strip()
    if response:
        readable = _humanize(response)
        if readable:
            snippet = readable[:_MAX_STEP]
            if len(readable) > _MAX_STEP:
                snippet += "…"
            parts.append(snippet)

    return "\n".join(parts)


def _humanize(text: str) -> str:
    """Convert JSON agent responses to readable text; return '' on failure."""
    import json, re as _re

    stripped = text.strip()

    # Strip markdown code fence (```json ... ``` or ``` ... ```)
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        stripped = "\n".join(lines[1:end]).strip()

    if not (stripped.startswith("{") or stripped.startswith("[")):
        return text

    data = None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        # ponytail: try extracting the first {...} blob if response has trailing noise
        m = _re.search(r"\{.*\}", stripped, _re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                pass

    if not isinstance(data, dict):
        return ""

    parts: list[str] = []

    headline = (data.get("headline") or "").strip()
    if headline:
        parts.append(f"📋 {headline}")
    else:
        thoughts = data.get("thoughts") or ""
        if isinstance(thoughts, list):
            thoughts = " ".join(str(t) for t in thoughts)
        thoughts = thoughts.strip()
        if thoughts:
            parts.append(f"💭 {thoughts}")

    tool_name = (data.get("tool_name") or "").strip()
    tool_args: dict = data.get("tool_args") or {}

    if tool_name.startswith("revolt_"):
        return ""

    if tool_name:
        # Represent common tools in plain English; fall back to key=value pairs.
        if tool_name == "response":
            reply = (tool_args.get("text") or tool_args.get("content") or "").strip()
            if reply:
                parts.append(f"💬 {reply}")
        elif tool_name in ("call_subordinate", "delegate"):
            msg = (tool_args.get("message") or "").strip()
            parts.append(f"📤 Delegating: {msg}" if msg else "📤 Delegating to sub-agent")
        elif tool_name == "code_execution_tool":
            runtime = tool_args.get("runtime", "")
            code = (tool_args.get("code") or "").strip()
            label = f"⚡ Run ({runtime})" if runtime else "⚡ Run code"
            parts.append(f"{label}: `{code[:120]}{'…' if len(code) > 120 else ''}`")
        else:
            arg_summary = ", ".join(
                f"{k}={repr(v)[:60]}" for k, v in list(tool_args.items())[:4]
            )
            parts.append(f"🔧 `{tool_name}`({arg_summary})" if arg_summary else f"🔧 `{tool_name}`")

    return "\n".join(parts)

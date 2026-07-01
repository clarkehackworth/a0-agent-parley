"""Unit tests for core utilities. No frameworks, no fixtures.

Run: python tests/test_core.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.message_split import split_message
from core.formatting import ulid_to_timestamp, format_message
from core.keywords import extract_keywords, _STOPWORDS
from core.context_config import ContextWindowConfig
from core.context_window import _select_backfill, _within_age, _filter_msgs
from core.echo_prevention import mark_pending, record, was_sent_by_us, _PENDING, _SENT
from core.models import Message, User, Channel


def _msg(id, author_id="u1", content="", attachments=0):
    return Message(id=id, author_id=author_id, content=content, attachments_count=attachments)


# ── message_split ──────────────────────────────────────────────────────────────

def test_split_short():
    assert split_message("hello", 100) == ["hello"]

def test_split_on_space():
    assert split_message("hello world", 5) == ["hello", "world"]

def test_split_on_newline():
    text = "line1\nline2\nline3"
    parts = split_message(text, 12)
    assert all(len(p) <= 12 for p in parts)
    assert len(parts) > 0

def test_split_hard_cut():
    word = "a" * 10
    parts = split_message(word, 3)
    assert all(len(p) <= 3 for p in parts)
    assert "".join(parts) == word

def test_split_no_infinite_loop():
    text = " " + "x" * 10
    parts = split_message(text, 3)
    assert len(parts) > 0
    assert all(len(p) <= 3 for p in parts)


# ── formatting ─────────────────────────────────────────────────────────────────

def test_ulid_to_timestamp_produces_datetime():
    from datetime import datetime, timezone
    ts = ulid_to_timestamp("01HQZWX0000000000000000000")
    assert isinstance(ts, datetime)
    assert ts.tzinfo == timezone.utc

def test_format_message_basic():
    msg = _msg("01HQZWX0000000000000000000", author_id="u1", content="hello")
    result = format_message(msg, {"u1": "alice"})
    assert "alice" in result
    assert "hello" in result

def test_format_message_no_content_attachment():
    msg = _msg("01HQZWX0000000000000000000", content="", attachments=2)
    assert "attachment" in format_message(msg, {})

def test_format_message_system_message():
    msg = _msg("01HQZWX0000000000000000000", content="")
    assert "system" in format_message(msg, {})

def test_format_message_unknown_user():
    msg = _msg("01HQZWX0000000000000000000", author_id="ABCDEF12", content="hi")
    result = format_message(msg, {})
    assert "ABCDEF1" in result


# ── keywords ──────────────────────────────────────────────────────────────────

def test_extract_keywords_basic():
    msgs = [_msg("a", content="deployment pipeline monitoring dashboard metrics alerts")]
    kw = extract_keywords(msgs)
    assert "deployment" in kw
    assert "monitoring" in kw

def test_extract_keywords_filters_stopwords():
    msgs = [_msg("a", content="this that with have from they will")]
    kw = extract_keywords(msgs)
    assert not any(w in _STOPWORDS for w in kw)

def test_extract_keywords_strips_urls():
    msgs = [_msg("a", content="check https://example.com/dashboard for metrics")]
    kw = extract_keywords(msgs)
    assert not any("http" in w for w in kw)
    assert "metrics" in kw

def test_extract_keywords_empty():
    assert extract_keywords([]) == []
    assert extract_keywords([_msg("a", content="")]) == []


# ── context_config ─────────────────────────────────────────────────────────────

def test_context_config_defaults():
    cfg = ContextWindowConfig()
    assert cfg.recent_limit == 25
    assert cfg.search_limit == 15
    assert cfg.include_first is True

def test_context_config_from_dict():
    cfg = ContextWindowConfig.from_dict({"recent_limit": "10", "max_age_days": "7.5", "include_pinned": False})
    assert cfg.recent_limit == 10
    assert cfg.max_age_days == 7.5
    assert cfg.include_pinned is False
    assert cfg.neighbors == 2


# ── context_window helpers ────────────────────────────────────────────────────

def test_select_backfill_ordering():
    hits = [_msg("a"), _msg("b"), _msg("c")]
    groups = [[_msg("a"), _msg("x")], [_msg("y")]]
    assert [m.id for m in _select_backfill(hits, groups, 10)] == ["a", "x", "b", "y", "c"]

def test_select_backfill_cap():
    hits = [_msg("a"), _msg("b"), _msg("c")]
    groups = [[_msg("x")], [_msg("y")]]
    assert len(_select_backfill(hits, groups, 2)) == 2

def test_select_backfill_dedup():
    hits = [_msg("a"), _msg("a")]
    assert len(_select_backfill(hits, [], 10)) == 1

def test_select_backfill_empty():
    assert _select_backfill([], [], 5) == []

def test_within_age_no_limit():
    assert _within_age(_msg("01HQZWX0000000000000000000"), 0.0) is True

def test_filter_msgs_bot_status():
    msgs = [
        _msg("a", author_id="bot", content="⚙️ Working on it…"),
        _msg("b", author_id="user"),
    ]
    result = _filter_msgs(msgs, bot_id="bot", max_age_days=0)
    assert len(result) == 1 and result[0].author_id == "user"

def test_filter_msgs_bot_non_status_kept():
    msgs = [_msg("a", author_id="bot", content="hello"), _msg("b", author_id="user")]
    result = _filter_msgs(msgs, bot_id="bot", max_age_days=0)
    assert len(result) == 2


# ── echo_prevention ───────────────────────────────────────────────────────────

def _reset_echo():
    _PENDING.clear()
    _SENT.clear()

def test_echo_layer1_pending():
    _reset_echo()
    mark_pending("ch", "hello")
    assert was_sent_by_us("", "ch", "hello")

def test_echo_layer1_consumed():
    _reset_echo()
    mark_pending("ch", "hello")
    was_sent_by_us("", "ch", "hello")
    assert not was_sent_by_us("", "ch", "hello")

def test_echo_layer2_id():
    _reset_echo()
    record("msg123")
    assert was_sent_by_us("msg123")
    assert was_sent_by_us("msg123")  # IDs not consumed

def test_echo_no_false_positive():
    _reset_echo()
    assert not was_sent_by_us("unknown", "ch", "not sent")


# ── models ────────────────────────────────────────────────────────────────────

def test_message_from_dict():
    m = Message.from_dict({"_id": "abc", "author": "u1", "content": "  hello  ", "attachments": [{}, {}]})
    assert m.id == "abc"
    assert m.content == "hello"
    assert m.attachments_count == 2

def test_message_from_dict_empty_content():
    m = Message.from_dict({"_id": "x", "author": "u", "content": None})
    assert m.content == ""

def test_user_from_dict():
    u = User.from_dict({"_id": "u1", "username": "alice"})
    assert u.id == "u1" and u.username == "alice"

def test_channel_from_dict():
    ch = Channel.from_dict({"_id": "c1", "name": "general"})
    assert ch.channel_type == "TextChannel"

def test_channel_preserves_type():
    ch = Channel.from_dict({"_id": "c1", "name": "voice", "channel_type": "VoiceChannel"})
    assert ch.channel_type == "VoiceChannel"


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)

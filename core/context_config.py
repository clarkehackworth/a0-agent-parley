"""ContextWindowConfig — typed config for build_context_window.

Replaces the flat kwargs spread across callers. Load from a raw config dict
via from_dict(), or override per-call by constructing directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContextWindowConfig:
    recent_limit: int = 25
    search_limit: int = 15
    max_age_days: float = 30.0
    neighbors: int = 2
    expand_top: int = 3
    include_first: bool = True
    include_pinned: bool = True
    min_keyword_length: int = 4

    @classmethod
    def from_dict(cls, d: dict) -> "ContextWindowConfig":
        return cls(
            recent_limit=int(d.get("recent_limit", 25)),
            search_limit=int(d.get("search_limit", 15)),
            max_age_days=float(d.get("max_age_days", 30.0)),
            neighbors=int(d.get("neighbors", 2)),
            expand_top=int(d.get("expand_top", 3)),
            include_first=bool(d.get("include_first", True)),
            include_pinned=bool(d.get("include_pinned", True)),
            min_keyword_length=int(d.get("min_keyword_length", 4)),
        )


if __name__ == "__main__":
    cfg = ContextWindowConfig.from_dict({"recent_limit": "10", "max_age_days": "7.5"})
    assert cfg.recent_limit == 10
    assert cfg.max_age_days == 7.5
    assert cfg.neighbors == 2  # default
    print("ok context_config")

"""Keyword extraction from message sets for context-window backfill search."""

from __future__ import annotations

import re
import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from usr.plugins.parley.core.models import Message

_STOPWORDS = {
    "this", "that", "with", "have", "from", "they", "will", "been", "were",
    "said", "each", "which", "their", "there", "about", "would", "these",
    "other", "into", "then", "than", "when", "what", "some", "also", "like",
    "just", "more", "very", "your", "here", "could", "should", "after",
    "before", "where", "only", "over", "such", "even", "back", "good",
    "much", "well", "need", "want", "make", "know", "does", "done", "think",
    "going", "dont", "cant", "isnt", "wasnt", "http", "https", "the", "and",
    "for", "are", "but", "not", "you", "all", "can", "her", "was", "one",
    "our", "out", "day", "get", "has", "him", "his", "how", "its", "may",
    "new", "now", "old", "see", "two", "way", "who", "boy", "did", "let",
    "put", "say", "she", "too", "use",
}


def extract_keywords(messages: "list[Message]", min_length: int = 4, top_n: int = 6) -> list[str]:
    """Extract the most significant words from a set of messages for backfill search."""
    freq: dict[str, int] = {}
    for msg in messages:
        text = re.sub(r"https?://\S+", "", msg.content)
        words = re.split(r"[\s" + re.escape(string.punctuation) + r"]+", text.lower())
        for word in words:
            word = word.strip()
            if len(word) >= min_length and word not in _STOPWORDS and word.isalpha():
                freq[word] = freq.get(word, 0) + 1
    ranked = sorted((w for w, c in freq.items() if c >= 1), key=lambda w: -freq[w])
    return ranked[:top_n]

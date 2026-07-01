"""Shared message splitting — replaces _split() duplicated across tools, extensions, and APIs."""


def split_message(text: str, limit: int) -> list[str]:
    """Split text into chunks no longer than limit, breaking on newlines then spaces."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:  # no split point found — hard cut; never 0 to ensure progress
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks


if __name__ == "__main__":
    assert split_message("hello", 10) == ["hello"]
    assert split_message("hello world", 5) == ["hello", "world"]
    long = "word " * 500
    parts = split_message(long, 100)
    assert all(len(p) <= 100 for p in parts), max(map(len, parts))
    print("ok split")

from gitpilot.chunker import chunk_text


def test_chunk_boundaries_and_overlap():
    # 250 lines, windows of 100 with 20 shared lines
    text = "\n".join(f"line {i}" for i in range(1, 251))
    chunks = chunk_text("owner/repo", "a.py", text, max_lines=100, overlap=20)

    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 100
    assert chunks[1].start_line == 81        # 20-line overlap with chunk 1
    assert chunks[-1].end_line == 250        # reaches the last line exactly

    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))         # every chunk id is unique


def test_chunk_short_file_single_chunk():
    chunks = chunk_text("owner/repo", "b.py", "print('hi')", max_lines=100)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 1
    assert chunks[0].citation == "b.py (lines 1-1)"


def test_chunk_empty_file_returns_nothing():
    assert chunk_text("owner/repo", "empty.py", "") == []


def test_overlap_must_be_smaller_than_window():
    import pytest

    with pytest.raises(ValueError):
        chunk_text("owner/repo", "x.py", "a\nb", max_lines=10, overlap=10)

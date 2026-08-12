"""Split source files into overlapping, line-based chunks.

Line-based chunking keeps citations honest: every chunk knows exactly
which file and which line range it came from.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    repo_id: str
    path: str
    start_line: int  # 1-based, inclusive
    end_line: int    # 1-based, inclusive
    text: str

    @property
    def chunk_id(self) -> str:
        return f"{self.repo_id}:{self.path}:{self.start_line}-{self.end_line}"

    @property
    def citation(self) -> str:
        return f"{self.path} (lines {self.start_line}-{self.end_line})"


def chunk_text(
    repo_id: str,
    path: str,
    text: str,
    max_lines: int = 120,
    overlap: int = 20,
) -> list[Chunk]:
    """Split `text` into chunks of at most `max_lines` with `overlap` shared lines."""
    if overlap >= max_lines:
        raise ValueError("overlap must be smaller than max_lines")
    lines = text.splitlines()
    if not lines:
        return []
    chunks: list[Chunk] = []
    start = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        chunks.append(
            Chunk(
                repo_id=repo_id,
                path=path,
                start_line=start + 1,
                end_line=end,
                text="\n".join(lines[start:end]),
            )
        )
        if end == len(lines):
            break
        start = end - overlap
    return chunks

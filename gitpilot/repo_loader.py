"""Clone a GitHub repo and walk its source files safely."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import config

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".sql", ".sh", ".yaml", ".yml", ".toml", ".md",
}
IGNORE_DIRS = {
    ".git", ".github", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
}
MAX_FILE_BYTES = 200_000  # skip huge or generated files


def repo_id_from_url(url: str) -> str:
    """'https://github.com/owner/repo(.git)' -> 'owner/repo'."""
    cleaned = url.strip().removesuffix(".git").rstrip("/")
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+)$", cleaned)
    if not match:
        raise ValueError(f"Not a valid GitHub URL: {url}")
    return f"{match.group(1)}/{match.group(2)}"


def clone_repo(url: str, repo_id: str, force: bool = False) -> Path:
    """Shallow-clone (depth 1) into the data dir; reuse if already cloned."""
    dest = config.REPOS_DIR / repo_id
    if dest.exists():
        if force:
            shutil.rmtree(dest)
        else:
            return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git clone failed: {proc.stderr.strip()}")
    return dest


def iter_code_files(root: Path):
    """Yield every supported source file, relative to the repo root."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield rel


def read_file(root: Path, rel_path: str) -> str:
    """Read a file inside the repo - with a path-traversal guard."""
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise ValueError(f"Path escapes the repository: {rel_path}")
    if not target.is_file():
        raise FileNotFoundError(rel_path)
    return target.read_text(encoding="utf-8", errors="replace")

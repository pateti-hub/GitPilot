"""The agent's toolbox: JSON schemas (what the LLM sees) + implementations.

Each tool is a small, auditable action. The agent loop stays dumb:
all intelligence lives in the model, all power lives in these functions.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..rag import search_code
from ..repo_loader import read_file
from . import github_client, sandbox

MAX_READ_LINES = 400
MAX_WRITE_BYTES = 100_000

# ---------------------------------------------------------------- schemas
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Semantic search over the repository's code. "
                "Returns matching snippets with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to look for, e.g. 'authentication logic'",
                    },
                    "top_k": {"type": "integer", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the repository (first 400 lines).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repo-relative path"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write the FULL new content of a file (create or overwrite). "
                "Always read the file first before overwriting it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repo-relative path"},
                    "content": {"type": "string", "description": "Complete file content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": (
                "Run the repository's pytest suite in a sandboxed subprocess "
                "and return pass/fail plus the output."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_pull_request",
            "description": (
                "Push all files changed so far to a new branch and open a "
                "pull request. Only call this when tests pass AND the user "
                "allowed pull requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "PR description (markdown)"},
                },
                "required": ["title", "body"],
            },
        },
    },
]


# ---------------------------------------------------------------- context
@dataclass
class ToolContext:
    """Everything a tool needs, plus the state the agent accumulates."""

    repo_id: str
    repo_path: Path
    allow_pr: bool = False
    changed_files: dict[str, str] = field(default_factory=dict)
    last_test_result: dict | None = None
    pr_url: str | None = None


# ---------------------------------------------------------------- implementations
def _search_code(ctx: ToolContext, query: str, top_k: int = 6) -> dict:
    return {"results": search_code(ctx.repo_id, query, top_k=min(top_k, 10))}


def _read_file(ctx: ToolContext, path: str) -> dict:
    text = read_file(ctx.repo_path, path)
    lines = text.splitlines()
    truncated = len(lines) > MAX_READ_LINES
    if truncated:
        text = "\n".join(lines[:MAX_READ_LINES])
    return {"path": path, "content": text, "truncated": truncated,
            "total_lines": len(lines)}


def _write_file(ctx: ToolContext, path: str, content: str) -> dict:
    if len(content.encode()) > MAX_WRITE_BYTES:
        raise ValueError("Refusing to write a file larger than 100 KB.")
    target = (ctx.repo_path / path).resolve()
    if not str(target).startswith(str(ctx.repo_path.resolve())):
        raise ValueError(f"Path escapes the repository: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    ctx.changed_files[path] = content
    return {"written": path, "bytes": len(content.encode())}


def _run_tests(ctx: ToolContext) -> dict:
    result = sandbox.run_tests(ctx.repo_path)
    ctx.last_test_result = result
    return result


def _open_pull_request(ctx: ToolContext, title: str, body: str) -> dict:
    if not ctx.allow_pr:
        return {"error": "Pull requests were not allowed for this run."}
    if not ctx.changed_files:
        return {"error": "No files changed yet - nothing to open a PR with."}
    branch = f"gitpilot/change-{int(time.time())}"
    url = github_client.open_pull_request(
        ctx.repo_id, branch, title, body, ctx.changed_files
    )
    ctx.pr_url = url
    return {"pull_request_url": url, "branch": branch}


_DISPATCH = {
    "search_code": _search_code,
    "read_file": _read_file,
    "write_file": _write_file,
    "run_tests": _run_tests,
    "open_pull_request": _open_pull_request,
}


def dispatch(ctx: ToolContext, name: str, arguments: dict) -> str:
    """Run one tool call; errors go back to the agent as data, not crashes."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        return json.dumps(fn(ctx, **arguments))
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})

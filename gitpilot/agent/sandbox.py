"""Run a repo's test suite in an isolated subprocess with a hard timeout.

Safety note (a great interview point): the sandbox only ever runs pytest,
inside the cloned repo, with shell=False. It never executes arbitrary
LLM-generated shell commands - least privilege by design.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .. import config


def run_tests(repo_path: Path, timeout: int | None = None) -> dict:
    timeout = timeout or config.TEST_TIMEOUT_SECONDS
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "output": f"Tests timed out after {timeout} seconds.",
        }
    except FileNotFoundError:
        return {
            "passed": False,
            "output": "pytest is not installed in this environment.",
        }
    output = (proc.stdout + proc.stderr).strip()
    return {
        "passed": proc.returncode == 0,
        "output": output[-4000:] if output else "(no output)",
    }

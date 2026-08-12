"""The agent loop: plan -> act -> observe, with a hard step limit.

This is the ReAct pattern in production form: the model decides which
tool to call next, we execute it, feed the result back, and repeat -
until the model writes a final summary or hits MAX_AGENT_STEPS.
"""
from __future__ import annotations

import json
import logging

from .. import config
from ..llm import get_client
from ..repo_loader import clone_repo
from .tools import TOOL_SCHEMAS, ToolContext, dispatch

logger = logging.getLogger("gitpilot.agent")

AGENT_SYSTEM_PROMPT = """You are GitPilot, an autonomous senior engineer
working inside a cloned repository.

Workflow you MUST follow:
1. Use search_code and read_file to understand the relevant code BEFORE
   writing anything. Never guess file contents.
2. Make the SMALLEST change that satisfies the task, using write_file.
3. ALWAYS call run_tests after changing code. If tests fail, read the
   output, fix your change, and run them again.
4. Only when tests pass (or the repo has no tests), call
   open_pull_request - and only if pull requests are allowed.

Rules:
- Never edit tests to make failures disappear unless the task says so.
- Keep every change minimal and readable.
- When finished, reply with a short summary: what changed, why, and the
  test result."""


def _result(ctx: ToolContext, summary: str, steps: int) -> dict:
    tests = ctx.last_test_result or {}
    return {
        "summary": summary,
        "files_changed": sorted(ctx.changed_files),
        "tests_passed": tests.get("passed"),
        "test_output": tests.get("output", ""),
        "pull_request_url": ctx.pr_url,
        "steps_taken": steps,
    }


def run_change_agent(
    repo_id: str,
    repo_url: str,
    instruction: str,
    open_pr: bool = False,
) -> dict:
    repo_path = clone_repo(repo_url, repo_id)
    ctx = ToolContext(repo_id=repo_id, repo_path=repo_path, allow_pr=open_pr)
    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Repository: {repo_id}\n"
                f"Pull requests allowed: {open_pr}\n\n"
                f"Task: {instruction}"
            ),
        },
    ]

    client = get_client()
    for step in range(1, config.MAX_AGENT_STEPS + 1):
        logger.info("agent step %d for %s", step, repo_id)
        response = client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            # No tool call -> the model wrote its final summary.
            return _result(ctx, message.content or "", step)

        for call in message.tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            logger.info("  tool: %s %s", call.function.name, arguments)
            result = dispatch(ctx, call.function.name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

    return _result(
        ctx,
        "Stopped: reached the maximum number of agent steps "
        f"({config.MAX_AGENT_STEPS}).",
        config.MAX_AGENT_STEPS,
    )

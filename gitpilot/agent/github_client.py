"""Minimal GitHub REST client: create branch -> commit files -> open PR.

Uses the Contents API so no local git credentials are needed - only the
GITHUB_TOKEN from your .env (needs the 'repo' scope).
"""
from __future__ import annotations

import base64

import httpx

from .. import config

API_BASE = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


def _headers() -> dict:
    if not config.GITHUB_TOKEN:
        raise GitHubError(
            "GITHUB_TOKEN is not set. Add it to your .env file to open "
            "pull requests (GitHub -> Settings -> Developer settings -> "
            "Personal access token, 'repo' scope)."
        )
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def open_pull_request(
    repo_id: str,
    branch: str,
    title: str,
    body: str,
    files: dict[str, str],
) -> str:
    """Push `files` to a new `branch` on repo_id and open a PR. Returns the PR URL."""
    with httpx.Client(base_url=API_BASE, headers=_headers(), timeout=30) as client:
        repo = client.get(f"/repos/{repo_id}")
        if repo.status_code != 200:
            raise GitHubError(f"Cannot read repo {repo_id}: {repo.text}")
        default_branch = repo.json()["default_branch"]

        ref = client.get(f"/repos/{repo_id}/git/ref/heads/{default_branch}")
        if ref.status_code != 200:
            raise GitHubError(f"Cannot read branch {default_branch}: {ref.text}")
        base_sha = ref.json()["object"]["sha"]

        created = client.post(
            f"/repos/{repo_id}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        if created.status_code not in (200, 201, 422):  # 422 = branch exists
            raise GitHubError(f"Cannot create branch {branch}: {created.text}")

        for path, content in files.items():
            existing = client.get(
                f"/repos/{repo_id}/contents/{path}", params={"ref": branch}
            )
            payload = {
                "message": f"gitpilot: update {path}",
                "content": base64.b64encode(content.encode()).decode(),
                "branch": branch,
            }
            if existing.status_code == 200:
                payload["sha"] = existing.json()["sha"]  # required to overwrite
            put = client.put(f"/repos/{repo_id}/contents/{path}", json=payload)
            if put.status_code not in (200, 201):
                raise GitHubError(f"Cannot commit {path}: {put.text}")

        pr = client.post(
            f"/repos/{repo_id}/pulls",
            json={"title": title, "head": branch, "base": default_branch,
                  "body": body},
        )
        if pr.status_code == 422:  # a PR for this branch already exists
            owner = repo_id.split("/")[0]
            pulls = client.get(
                f"/repos/{repo_id}/pulls",
                params={"head": f"{owner}:{branch}", "state": "open"},
            )
            if pulls.status_code == 200 and pulls.json():
                return pulls.json()[0]["html_url"]
            raise GitHubError(f"PR already exists but could not be fetched: {pr.text}")
        if pr.status_code != 201:
            raise GitHubError(f"Cannot open pull request: {pr.text}")
        return pr.json()["html_url"]

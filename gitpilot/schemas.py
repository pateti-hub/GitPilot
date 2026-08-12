"""Pydantic models: the API contract.

Bad input is rejected here with a clear 422 error - it never reaches the
business logic. This is the 'validate at the boundary' principle.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class IndexRepoRequest(BaseModel):
    repo_url: str = Field(..., examples=["https://github.com/psf/requests"])
    force: bool = False  # set true to re-clone and re-index from scratch


class IndexRepoResponse(BaseModel):
    repo_id: str
    files_indexed: int
    chunks_indexed: int


class RepoInfo(BaseModel):
    repo_id: str
    repo_url: str
    status: str
    files_indexed: int
    chunks_indexed: int
    indexed_at: str


class AskRequest(BaseModel):
    repo_id: str = Field(..., examples=["psf/requests"])
    question: str = Field(..., min_length=3)
    top_k: int = Field(6, ge=1, le=20)


class Citation(BaseModel):
    path: str
    start_line: int
    end_line: int


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    cached: bool


class ChangeRequest(BaseModel):
    repo_id: str = Field(..., examples=["psf/requests"])
    instruction: str = Field(..., min_length=5)
    open_pr: bool = False  # requires GITHUB_TOKEN in .env


class ChangeResponse(BaseModel):
    summary: str
    files_changed: list[str]
    tests_passed: bool | None
    test_output: str
    pull_request_url: str | None
    steps_taken: int

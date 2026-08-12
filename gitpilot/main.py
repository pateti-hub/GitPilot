"""GitPilot's HTTP API.

Endpoints:
    GET  /health         - liveness probe
    POST /repos/index    - clone + index a GitHub repository
    GET  /repos          - list everything indexed so far
    POST /ask            - ask a question about an indexed repo (RAG + cache)
    POST /changes        - let the agent edit code, run tests, open a PR

Interactive docs: http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import config
from .agent.loop import run_change_agent
from .db import get_repo, init_db, list_repos
from .indexer import index_repository
from .rag import answer_question
from .repo_loader import repo_id_from_url
from .schemas import (
    AskRequest,
    AskResponse,
    ChangeRequest,
    ChangeResponse,
    IndexRepoRequest,
    IndexRepoResponse,
    RepoInfo,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("gitpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("GitPilot ready - docs at http://localhost:8000/docs")
    yield


app = FastAPI(
    title="GitPilot",
    version="0.1.0",
    description="An AI agent that understands any GitHub repository.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "openai_key_set": bool(config.OPENAI_API_KEY)}


@app.post("/repos/index", response_model=IndexRepoResponse)
async def index_repo_endpoint(req: IndexRepoRequest) -> IndexRepoResponse:
    try:
        repo_id = repo_id_from_url(req.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Indexing %s ...", repo_id)
    try:
        # indexing is blocking work (clone + embeddings) -> run it in a
        # thread so the event loop keeps serving other requests
        stats = await asyncio.to_thread(
            index_repository, req.repo_url, repo_id, req.force
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return IndexRepoResponse(**stats)


@app.get("/repos", response_model=list[RepoInfo])
def list_repos_endpoint() -> list[dict]:
    return list_repos()


@app.post("/ask", response_model=AskResponse)
async def ask_endpoint(req: AskRequest) -> AskResponse:
    if not get_repo(req.repo_id):
        raise HTTPException(
            status_code=404,
            detail=f"{req.repo_id} has not been indexed. "
            "POST /repos/index first.",
        )
    result = await asyncio.to_thread(
        answer_question, req.repo_id, req.question, req.top_k
    )
    return AskResponse(**result)


@app.post("/changes", response_model=ChangeResponse)
async def change_endpoint(req: ChangeRequest) -> ChangeResponse:
    repo = get_repo(req.repo_id)
    if not repo:
        raise HTTPException(
            status_code=404,
            detail=f"{req.repo_id} has not been indexed. "
            "POST /repos/index first.",
        )
    if req.open_pr and not config.GITHUB_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="Set GITHUB_TOKEN in your .env file to open pull requests.",
        )
    result = await asyncio.to_thread(
        run_change_agent, req.repo_id, repo["repo_url"], req.instruction, req.open_pr
    )
    return ChangeResponse(**result)

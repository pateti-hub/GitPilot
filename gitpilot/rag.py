"""Question answering over an indexed repo: retrieval -> grounded answer.

Every answer carries citations (file + line range) and repeat questions
are served from the cache for free.
"""
from __future__ import annotations

from . import config
from .cache import get_cache, make_key
from .indexer import embed_texts, get_collection
from .llm import get_client

SYSTEM_PROMPT = """You are GitPilot, a senior engineer explaining a codebase.
Rules:
- Answer ONLY from the code snippets provided. Never invent code.
- Cite every claim inline like this: [path/to/file.py lines 10-25]
- If the snippets do not contain the answer, say so honestly.
- Be concrete and concise. Quote small pieces of code when helpful."""


def search_code(repo_id: str, query: str, top_k: int = 6) -> list[dict]:
    """Semantic search over one repo. Used by both /ask and the agent."""
    query_embedding = embed_texts([query])[0]
    results = get_collection().query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"repo_id": repo_id},
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    hits = []
    for doc, meta in zip(documents, metadatas):
        hits.append(
            {
                "path": meta["path"],
                "start_line": meta["start_line"],
                "end_line": meta["end_line"],
                "snippet": doc[:1500],
            }
        )
    return hits


def answer_question(repo_id: str, question: str, top_k: int = 6) -> dict:
    """The full RAG flow: cache check -> retrieve -> generate -> cache."""
    cache = get_cache()
    key = make_key("ask", repo_id, question, str(top_k), config.CHAT_MODEL)
    hit = cache.get(key)
    if hit:
        hit["cached"] = True
        return hit

    hits = search_code(repo_id, question, top_k=top_k)
    if not hits:
        return {
            "answer": (
                "This repository has not been indexed yet (or it contains "
                "no supported source files). Run POST /repos/index first."
            ),
            "citations": [],
            "cached": False,
        }

    context_blocks = []
    citations = []
    for hit in hits:
        label = f"{hit['path']} lines {hit['start_line']}-{hit['end_line']}"
        context_blocks.append(f"### {label}\n```\n{hit['snippet']}\n```")
        citations.append(
            {
                "path": hit["path"],
                "start_line": hit["start_line"],
                "end_line": hit["end_line"],
            }
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Code snippets:\n\n"
                + "\n\n".join(context_blocks)
                + f"\n\nQuestion: {question}"
            ),
        },
    ]
    response = get_client().chat.completions.create(
        model=config.CHAT_MODEL, messages=messages, temperature=0
    )
    payload = {
        "answer": response.choices[0].message.content,
        "citations": citations,
        "cached": False,
    }
    cache.set(key, payload, ttl_seconds=3600)
    return payload

"""Turn a cloned repository into a searchable vector index (Chroma)."""
from __future__ import annotations

from . import config
from .chunker import Chunk, chunk_text
from .db import upsert_repo
from .llm import get_client
from .repo_loader import clone_repo, iter_code_files, read_file

EMBED_BATCH_SIZE = 96   # stay comfortably under the API's input limits
UPSERT_BATCH_SIZE = 256  # Chroma prefers moderate batch sizes
COLLECTION_NAME = "gitpilot_code"

_client = None


def get_collection():
    """One persistent Chroma collection, shared by the whole app."""
    global _client
    if _client is None:
        import chromadb  # lazy import: it is a heavy dependency

        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts in batches with the configured embedding model."""
    client = get_client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        response = client.embeddings.create(
            model=config.EMBEDDING_MODEL, input=batch
        )
        vectors.extend(item.embedding for item in response.data)
    return vectors


def index_repository(repo_url: str, repo_id: str, force: bool = False) -> dict:
    """Clone -> chunk -> embed -> store. Safe to run twice (idempotent)."""
    root = clone_repo(repo_url, repo_id, force=force)

    chunks: list[Chunk] = []
    files = 0
    for rel_path in iter_code_files(root):
        text = read_file(root, str(rel_path))
        chunks.extend(chunk_text(repo_id, str(rel_path), text))
        files += 1

    if not chunks:
        upsert_repo(repo_id, repo_url, status="empty")
        return {"repo_id": repo_id, "files_indexed": 0, "chunks_indexed": 0}

    collection = get_collection()
    # wipe any previous index for this repo so re-indexing is idempotent
    collection.delete(where={"repo_id": repo_id})

    embeddings = embed_texts([chunk.text for chunk in chunks])

    for i in range(0, len(chunks), UPSERT_BATCH_SIZE):
        part = chunks[i : i + UPSERT_BATCH_SIZE]
        collection.upsert(
            ids=[c.chunk_id for c in part],
            embeddings=embeddings[i : i + UPSERT_BATCH_SIZE],
            documents=[c.text for c in part],
            metadatas=[
                {
                    "repo_id": c.repo_id,
                    "path": c.path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                }
                for c in part
            ],
        )

    upsert_repo(
        repo_id, repo_url,
        status="indexed", files_indexed=files, chunks_indexed=len(chunks),
    )
    return {
        "repo_id": repo_id,
        "files_indexed": files,
        "chunks_indexed": len(chunks),
    }

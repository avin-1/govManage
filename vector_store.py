import os
from typing import Any, Dict, List, Optional

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    except ImportError as exc:
        raise RuntimeError("chromadb is required: pip install chromadb") from exc

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    client = chromadb.PersistentClient(path=persist_dir)
    _collection = client.get_or_create_collection(
        name="policy_chunks",
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def upsert_chunks(document_id: str, chunks: List[str], metadata: Dict[str, Any]) -> int:
    """Embed and store chunks for a policy document. Returns chunk count stored."""
    col = _get_collection()
    ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{**metadata, "document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    col.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def delete_document_chunks(document_id: str) -> None:
    """Remove all Chroma vectors for a given document."""
    col = _get_collection()
    col.delete(where={"document_id": document_id})


def search_chunks(
    query: str,
    n_results: int = 5,
    document_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Semantic search over policy chunks. Returns list of {text, metadata, distance}."""
    col = _get_collection()
    total = col.count()
    if total == 0:
        return []

    kwargs: Dict[str, Any] = {
        "query_texts": [query],
        "n_results": min(n_results, total),
    }
    if document_id:
        kwargs["where"] = {"document_id": document_id}

    results = col.query(**kwargs)
    hits = []
    for i, doc in enumerate(results["documents"][0]):
        hits.append(
            {
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            }
        )
    return hits

"""
RAG retrieval: semantic search over the product catalog in Qdrant. Owned by P2.

`search(query, k)` returns lightweight hits ({product_id, score, ...}); the caller
(app/retrieval/retriever.py) maps product_ids back to authoritative Product
objects (prices/stock from Postgres). Nothing here decides eligibility - it only
finds candidates by meaning.

The embedding model + Qdrant client are built lazily and cached, so importing
this module is cheap and the ~90 MB model only loads on first real search.

Manual test:  cd backend && python -m app.rag.retriever
"""
import logging
from functools import lru_cache

from app.config import (
    EMBED_MODEL,
    MODEL_CACHE_DIR,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _embeddings():
    """The ~90MB local embedding model. Cached separately from the Qdrant
    connection: lru_cache does NOT cache raised exceptions, so if it were bundled
    into _vector_store() below, a transient Qdrant hiccup would re-trigger a full
    model reload on every subsequent call, not just re-attempt the Qdrant part."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=EMBED_MODEL, cache_folder=MODEL_CACHE_DIR)


@lru_cache(maxsize=1)
def _vector_store():
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    return QdrantVectorStore(
        client=client,
        collection_name=QDRANT_COLLECTION,
        embedding=_embeddings(),
    )


def search(query: str, k: int = 8) -> list[dict]:
    """Semantic top-k search. Returns [{product_id, score, name, content}].
    Raises if Qdrant/deps are unavailable - callers decide how to fall back."""
    store = _vector_store()
    hits = store.similarity_search_with_score(query, k=k)
    results = []
    for doc, score in hits:
        md = doc.metadata or {}
        results.append({
            "product_id": md.get("product_id"),
            "score": float(score),
            "name": md.get("name", ""),
            "content": doc.page_content,
        })
    return results


def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    print("Product semantic search. Type 'exit' to quit.\n")
    while True:
        query = input("Search: ").strip()
        if query.lower() in {"exit", "quit", ""}:
            break
        for i, hit in enumerate(search(query, k=3), start=1):
            print(f"  {i}. {hit['name']}  [{hit['product_id']}]  score={hit['score']:.3f}")
        print()


if __name__ == "__main__":
    _main()

"""
RAG ingestion: embed the product catalog's semantic text into Qdrant. Owned by P2.

Only the descriptive fields live here (name/brand/description/features) - the
"required information in the vector DB". Prices/stock are NOT embedded; those are
volatile facts read live from Postgres at query time (see app/retrieval/catalog.py).
The metadata carries `product_id` (the slug) so a hit can be mapped back to the
authoritative Product.

Run:  cd backend && python -m app.rag.ingestion

Heavy imports are kept inside functions so importing this module (e.g. for tests)
never requires the ML stack.
"""
import json
import logging
import os
from uuid import uuid4

from app.config import EMBED_MODEL, QDRANT_COLLECTION, QDRANT_URL

logger = logging.getLogger(__name__)

_EMBED_DIM = 384  # all-MiniLM-L6-v2 output size
_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "products_vector.json")


def _build_document(product: dict):
    """One embedding document per product: description + features as the text to
    embed, ids/names as filterable metadata."""
    from langchain_core.documents import Document

    content = (
        f"{product.get('name', '')} by {product.get('brand', '')}. "
        f"{product.get('description', '')} "
        f"Features: {', '.join(product.get('features', []))}."
    ).strip()
    return Document(
        page_content=content,
        metadata={
            "product_id": product["id"],
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "type": product.get("type", ""),
            "category": product.get("category", ""),
        },
    )


def ingest(data_file: str = _DATA_FILE, recreate: bool = True) -> int:
    """(Re)build the Qdrant collection from the semantic catalog file.
    Returns the number of vectors stored."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams

    with open(data_file, "r", encoding="utf-8") as f:
        products = json.load(f)
    documents = [_build_document(p) for p in products]
    logger.info("Embedding %d products with %s...", len(documents), EMBED_MODEL)

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    client = QdrantClient(url=QDRANT_URL)

    if recreate and client.collection_exists(QDRANT_COLLECTION):
        client.delete_collection(QDRANT_COLLECTION)
    if not client.collection_exists(QDRANT_COLLECTION):
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=_EMBED_DIM, distance=Distance.COSINE),
        )

    store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION, embedding=embeddings)
    store.add_documents(documents=documents, ids=[str(uuid4()) for _ in documents])

    total = client.count(QDRANT_COLLECTION).count
    logger.info("Ingestion complete. Collection '%s' holds %d vectors.", QDRANT_COLLECTION, total)
    return total


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    ingest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

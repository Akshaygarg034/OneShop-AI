"""
Retrieval (RAG). Owned by P2.

EXPOSES:  retrieve(intent) -> list[Product]   (candidate products)

MOCK (now):  keyword match over the catalog.
REAL (P2):   embed catalog with sentence-transformers -> Qdrant; semantic top-k search.
             Put qdrant/sentence-transformers imports INSIDE the real function so
             mock mode never needs them installed.
"""
from app.config import MOCK_MODE
from app.contracts.models import Intent, Product
from app.retrieval.catalog import load_catalog


def retrieve(intent: Intent, top_k: int = 8) -> list[Product]:
    if MOCK_MODE:
        return _retrieve_mock(intent, top_k)
    return _retrieve_real(intent, top_k)


def _retrieve_mock(intent: Intent, top_k: int) -> list[Product]:
    """Naive keyword scoring so the demo feels alive before Qdrant is wired."""
    catalog = load_catalog()
    wanted_features = set(intent.priority_features)
    wanted_types = set(intent.product_types) or {"phone", "plan", "accessory"}

    def score(p: Product) -> int:
        s = 0
        if p.type.value in wanted_types:
            s += 2
        s += len(wanted_features.intersection(p.features))
        if any(w in p.description.lower() for w in intent.use_case.lower().split()):
            s += 1
        return s

    ranked = sorted(catalog, key=score, reverse=True)
    return ranked[:top_k]


def _retrieve_real(intent: Intent, top_k: int) -> list[Product]:
    """
    TODO (P2): implement semantic retrieval.
      1. Build a query string from the intent (use_case + priority_features).
      2. Embed it with the EMBED_MODEL.
      3. Query Qdrant for top_k nearest product ids.
      4. Map ids back to Product objects via app.retrieval.catalog.get_product.
    Import qdrant_client / sentence_transformers here (not at module top).
    """
    raise NotImplementedError("P2: implement Qdrant retrieval, then set MOCK_MODE=false")

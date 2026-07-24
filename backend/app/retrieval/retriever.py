"""
Retrieval (RAG). Owned by P2.

EXPOSES:  retrieve(intent) -> list[Product]   (candidate products)

Two paths, chosen by RAG_ENABLED (independent of MOCK_MODE so semantic search can
be real while intent/recommendation still run on their mocks):
  - RAG_ENABLED=false : keyword match over the catalog (fast, zero infra).
  - RAG_ENABLED=true  : semantic top-k from Qdrant (app/rag/retriever.py), then
                        map hits to authoritative Product objects. Falls back to
                        the keyword path if Qdrant / the ML deps are unavailable,
                        so turning it on can never break the demo.

Heavy imports stay inside app/rag so mock mode needs nothing installed.
"""
import logging

from app.config import RAG_ENABLED, QDRANT_API_KEY
from app.contracts.models import Intent, Product
from app.retrieval.catalog import get_product, load_catalog

logger = logging.getLogger(__name__)


def retrieve(intent: Intent, top_k: int = 8) -> list[Product]:
    if RAG_ENABLED:
        return _retrieve_semantic(intent, top_k)
    return _retrieve_mock(intent, top_k)


def _retrieve_mock(intent: Intent, top_k: int) -> list[Product]:
    """Naive keyword scoring so the demo feels alive without Qdrant."""
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


def _build_query(intent: Intent) -> str:
    parts = [intent.use_case or ""]
    parts.extend(intent.priority_features)
    parts.extend(intent.product_types)
    return " ".join(p for p in parts if p).strip() or "phone"


def _retrieve_semantic(intent: Intent, top_k: int) -> list[Product]:
    """Semantic retrieval from Qdrant, mapped back to authoritative Products.
    Any failure (deps missing, Qdrant down, empty collection) falls back to the
    keyword path - the assistant keeps working, just less 'smart'."""
    try:
        from app.rag.retriever import search
    except ImportError as e:  # ML deps not installed
        logger.warning("RAG deps unavailable (%s); using keyword retrieval.", e)
        return _retrieve_mock(intent, top_k)

    try:
        hits = search(_build_query(intent), k=top_k)
    except Exception as e:  # noqa - Qdrant unreachable / empty collection / etc.
        logger.warning("RAG search failed (%s); using keyword retrieval.", e)
        return _retrieve_mock(intent, top_k)

    products: list[Product] = []
    seen: set[str] = set()
    for hit in hits:
        pid = hit.get("product_id")
        if not pid or pid in seen:
            continue
        product = get_product(pid)   # authoritative prices/stock (Postgres/JSON)
        if product:
            products.append(product)
            seen.add(pid)

    if not products:
        logger.warning("RAG returned no mappable products; using keyword retrieval.")
        return _retrieve_mock(intent, top_k)
    return products

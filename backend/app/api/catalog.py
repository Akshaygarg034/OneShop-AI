"""
Read-only catalog endpoint. Owned by P2.
The frontend uses this to render product cards (name, price, stock).
"""
from fastapi import APIRouter, HTTPException

from app.contracts.models import Product
from app.retrieval.catalog import get_product, load_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=list[Product])
def all_products() -> list[Product]:
    return load_catalog()


@router.get("/{product_id}", response_model=Product)
def one_product(product_id: str) -> Product:
    p = get_product(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="product not found")
    return p

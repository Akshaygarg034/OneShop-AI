import os

os.environ["ENVIRONMENT"] = "test"
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["REQUIRE_LOGIN_FOR_CHAT"] = "false"  # guest-mode default for tests; the gate has its own test
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("AUTH_SECRET", "test-secret-not-for-production")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def product():
    from app.contracts.models import Product

    return Product(
        id="phone-test-1",
        type="phone",
        name="Test Phone 8/128",
        brand="Samsung",
        description="A test phone.",
        category="smartphones",
        price_onetime=599.0,
        original_price=649.0,
        discount_pct=8,
        rating=4.5,
        review_count=1200,
        colors=["black", "blue"],
        features=["5g", "camera"],
        stock=10,
        in_stock=True,
        popularity=0.8,
        attributes={"ram_gb": 8, "storage_gb": 128, "os": "android", "battery_mah": 4500},
    )

from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from app.main import app
from app.models import Base


def test_all_models_configure():
    configure_mappers()
    assert len(Base.metadata.tables) >= 40


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_contains_core_routes():
    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/products" in paths
    assert "/api/v1/purchase-requisitions" in paths
    assert "/api/v1/goods-receipts" in paths
    assert "/api/v1/inventory" in paths

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
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/products" in paths
    assert "/api/v1/purchase-requisitions" in paths
    assert "/api/v1/purchase-requisitions/{requisition_id}" in paths
    assert "/api/v1/purchase-requisitions/{requisition_id}/submit" in paths
    assert "/api/v1/purchase-requisitions/{requisition_id}/approve" in paths
    assert "/api/v1/purchase-requisitions/{requisition_id}/reject" in paths
    assert "/api/v1/approvals/{entity_type}/{entity_id}" in paths
    assert "get" in paths["/api/v1/purchase-requisitions/{requisition_id}"]
    assert "post" in paths["/api/v1/purchase-requisitions/{requisition_id}/submit"]
    assert "post" in paths["/api/v1/purchase-requisitions/{requisition_id}/approve"]
    assert "post" in paths["/api/v1/purchase-requisitions/{requisition_id}/reject"]
    assert "/api/v1/purchase-orders" in paths
    assert "/api/v1/purchase-orders/{purchase_order_id}" in paths
    assert "/api/v1/purchase-orders/{purchase_order_id}/submit" in paths
    assert "/api/v1/purchase-orders/{purchase_order_id}/approve" in paths
    assert "/api/v1/purchase-orders/{purchase_order_id}/reject" in paths
    assert "/api/v1/purchase-orders/{purchase_order_id}/cancel" in paths
    assert "/api/v1/purchase-requisitions/eligible-for-po" in paths
    assert "post" in paths["/api/v1/purchase-orders"]
    assert "post" in paths["/api/v1/purchase-orders/{purchase_order_id}/submit"]
    assert "post" in paths["/api/v1/purchase-orders/{purchase_order_id}/approve"]
    assert "post" in paths["/api/v1/purchase-orders/{purchase_order_id}/reject"]
    assert "/api/v1/goods-receipts" in paths
    assert "/api/v1/goods-receipts/{receipt_id}" in paths
    assert "/api/v1/warehouses" in paths
    assert "/api/v1/inventory/{inventory_id}" in paths
    assert "/api/v1/inventory/movements" in paths
    assert "/api/v1/audit/events" in paths
    assert "/api/v1/traceability/purchase-requisitions/{requisition_id}" in paths
    assert "/api/v1/traceability/purchase-orders/{purchase_order_id}" in paths
    assert "/api/v1/inventory" in paths
    assert "/api/v1/document-attachments/upload" in paths
    assert "/api/v1/document-attachments" in paths
    assert "/api/v1/document-attachments/{attachment_id}/download" in paths

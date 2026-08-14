from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.document_attachments import get_document_storage
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.document_attachment import DocumentAttachment
from app.models.purchase_requisition import PurchaseRequisition
from app.models.user import User
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.purchase_requisition import PurchaseRequisitionCreate
from app.services.file_storage import LocalFileStorage


PDF_BYTES = b"%PDF-1.4\nminimal test document\n%%EOF\n"


@pytest.fixture
def attachment_client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'attachments.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine)
    for table in (
        User.__table__,
        PurchaseRequisition.__table__,
        DocumentAttachment.__table__,
    ):
        table.create(engine)

    with session_factory() as db:
        db.add(
            User(
                id=1,
                username="finance-test",
                email="finance@example.test",
                full_name="Finance Test",
                password_hash="unused",
                is_active=True,
            )
        )
        db.add(
            PurchaseRequisition(
                id=1,
                pr_number="PR-TEST-1",
                request_date=date(2024, 1, 2),
                status="DRAFT",
                total_amount=0,
                source_type="LIVE",
            )
        )
        db.commit()

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_document_storage] = lambda: LocalFileStorage(
        tmp_path / "uploads"
    )
    monkeypatch.setattr(
        "app.api.v1.document_attachments.ActivityService.log",
        lambda **_: None,
    )
    try:
        yield TestClient(app), session_factory, tmp_path / "uploads"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def upload_pdf(client: TestClient):
    return client.post(
        "/api/v1/document-attachments/upload",
        data={
            "entity_type": "PURCHASE_REQUISITION",
            "entity_id": "1",
            "attachment_type": "INVOICE_SUPPORT",
        },
        files={"file": ("../support.pdf", PDF_BYTES, "application/pdf")},
    )


def test_upload_and_list_pdf_attachment(attachment_client):
    client, _, _ = attachment_client
    uploaded = upload_pdf(client)
    assert uploaded.status_code == 201
    payload = uploaded.json()
    assert payload["original_file_name"] == "support.pdf"
    assert payload["checksum_sha256"]
    assert "storage_path" not in payload
    assert "stored_file_name" not in payload

    listed = client.get(
        "/api/v1/document-attachments",
        params={"entity_type": "PURCHASE_REQUISITION", "entity_id": 1},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [payload["id"]]


def test_download_pdf_attachment(attachment_client):
    client, _, _ = attachment_client
    attachment_id = upload_pdf(client).json()["id"]
    response = client.get(
        f"/api/v1/document-attachments/{attachment_id}/download"
    )
    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"


def test_rejects_unsupported_mime_type(attachment_client):
    client, _, _ = attachment_client
    response = client.post(
        "/api/v1/document-attachments/upload",
        data={
            "entity_type": "PURCHASE_REQUISITION",
            "entity_id": "1",
            "attachment_type": "OTHER",
        },
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_rejects_nonexistent_entity(attachment_client):
    client, _, _ = attachment_client
    response = client.post(
        "/api/v1/document-attachments/upload",
        data={
            "entity_type": "PURCHASE_REQUISITION",
            "entity_id": "999",
            "attachment_type": "OTHER",
        },
        files={"file": ("support.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 404


def test_soft_delete_attachment(attachment_client):
    client, session_factory, uploads = attachment_client
    attachment_id = upload_pdf(client).json()["id"]
    response = client.delete(f"/api/v1/document-attachments/{attachment_id}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    with session_factory() as db:
        attachment = db.get(DocumentAttachment, attachment_id)
        assert attachment.is_active is False
        assert attachment.deleted_by_id == 1
        assert (uploads / attachment.storage_path).is_file()


def test_historical_inputs_retain_business_dates_and_references():
    pr = PurchaseRequisitionCreate(
        request_date=date(2020, 1, 2),
        source_type="HISTORICAL_IMPORT",
        external_reference="LEGACY-PR-9",
        items=[],
    )
    po = PurchaseOrderCreate(
        supplier_id=1,
        order_date=date(2020, 2, 3),
        source_type="HISTORICAL_IMPORT",
        external_reference="LEGACY-PO-8",
        expected_date=date(2020, 2, 10),
        purchase_requisition_ids=[1],
        items=[
            {
                "product_id": 1,
                "quantity": 1,
                "unit_price": 5,
                "purchase_requisition_item_id": 1,
            }
        ],
    )
    receipt_time = datetime(2020, 2, 11, 8, 30, tzinfo=timezone.utc)
    receipt = GoodsReceiptCreate(
        purchase_order_id=1,
        warehouse_id=1,
        received_at=receipt_time,
        source_type="HISTORICAL_IMPORT",
        external_reference="LEGACY-GR-7",
        items=[],
    )
    assert (pr.request_date, pr.external_reference) == (
        date(2020, 1, 2),
        "LEGACY-PR-9",
    )
    assert (po.order_date, po.external_reference) == (
        date(2020, 2, 3),
        "LEGACY-PO-8",
    )
    assert (receipt.received_at, receipt.external_reference) == (
        receipt_time,
        "LEGACY-GR-7",
    )

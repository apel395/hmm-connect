from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document_attachment import DocumentAttachment
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_requisition import PurchaseRequisition
from app.models.supplier_invoice import SupplierInvoice
from app.models.payment import Payment
from app.models.purchasing_document import PurchasingDocument
from app.schemas.document_attachment import DocumentAttachmentResponse
from app.services.activity_service import ActivityService
from app.services.file_storage import (
    EmptyFileError,
    FileStorageError,
    FileTooLargeError,
    LocalFileStorage,
)


router = APIRouter(prefix="/document-attachments", tags=["Document Attachments"])
ENTITY_MODELS = {
    "PURCHASE_REQUISITION": PurchaseRequisition,
    "PURCHASE_ORDER": PurchaseOrder,
    "GOODS_RECEIPT": GoodsReceipt,
    "PURCHASING_DOCUMENT": PurchasingDocument,
    "SUPPLIER_INVOICE": SupplierInvoice,
    "PAYMENT": Payment,
}
SOURCE_TYPES = {"LIVE", "HISTORICAL_IMPORT"}


def get_document_storage() -> LocalFileStorage:
    return LocalFileStorage(settings.DOCUMENT_STORAGE_PATH)


def normalized_entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().upper()
    if normalized not in ENTITY_MODELS:
        raise HTTPException(status_code=422, detail="Unsupported entity type")
    return normalized


def require_entity(db: Session, entity_type: str, entity_id: int) -> None:
    if not db.get(ENTITY_MODELS[entity_type], entity_id):
        raise HTTPException(status_code=404, detail="Referenced entity not found")


def sanitized_filename(filename: str | None) -> str:
    basename = Path(filename or "").name
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", basename).strip(" .")
    return (safe or "document")[:255]


def content_disposition(filename: str) -> str:
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", filename).replace('"', "_")
    return f'attachment; filename="{ascii_name or "document"}"'


def stream_file(file_handle):
    try:
        while chunk := file_handle.read(1024 * 1024):
            yield chunk
    finally:
        file_handle.close()


@router.post("/upload", response_model=DocumentAttachmentResponse, status_code=201)
def upload_attachment(
    entity_type: Annotated[str, Form()],
    entity_id: Annotated[int, Form(gt=0)],
    attachment_type: Annotated[str, Form(min_length=1, max_length=50)],
    file: Annotated[UploadFile, File()],
    document_number: Annotated[str | None, Form(max_length=100)] = None,
    document_date: Annotated[date | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    source_type: Annotated[str, Form()] = "LIVE",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    storage: LocalFileStorage = Depends(get_document_storage),
):
    entity_type = normalized_entity_type(entity_type)
    require_entity(db, entity_type, entity_id)
    source_type = source_type.strip().upper()
    if source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported source type")
    mime_type = (file.content_type or "").lower()
    if mime_type not in settings.allowed_document_mime_types:
        raise HTTPException(status_code=415, detail="Unsupported document MIME type")

    original_name = sanitized_filename(file.filename)
    extension = Path(original_name).suffix.lower()[:16]
    stored_name = f"{uuid4()}{extension}"
    now = datetime.now(timezone.utc)
    storage_path = (
        f"{entity_type.lower()}/{now.year:04d}/{now.month:02d}/{stored_name}"
    )
    try:
        file_size, checksum = storage.save(
            file.file,
            storage_path,
            max_bytes=settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024,
        )
    except EmptyFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=500, detail="Document storage failed") from exc

    attachment = DocumentAttachment(
        entity_type=entity_type,
        entity_id=entity_id,
        attachment_type=attachment_type,
        document_number=document_number,
        document_date=document_date,
        original_file_name=original_name,
        stored_file_name=stored_name,
        storage_provider="LOCAL",
        storage_path=storage_path,
        mime_type=mime_type,
        file_size=file_size,
        checksum_sha256=checksum,
        description=description,
        source_type=source_type,
        uploaded_by_id=user.id,
    )
    try:
        db.add(attachment)
        db.flush()
        ActivityService.log(
            db=db,
            user=user,
            action="ATTACH",
            entity_type=entity_type,
            entity_id=entity_id,
            summary=f"Uploaded supporting document {original_name}",
            details={"attachment_id": attachment.id, "attachment_type": attachment_type},
        )
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        storage.delete(storage_path)
        raise
    return attachment


@router.get("", response_model=list[DocumentAttachmentResponse])
def list_attachments(
    entity_type: str = Query(),
    entity_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    entity_type = normalized_entity_type(entity_type)
    require_entity(db, entity_type, entity_id)
    return (
        db.query(DocumentAttachment)
        .filter(
            DocumentAttachment.entity_type == entity_type,
            DocumentAttachment.entity_id == entity_id,
            DocumentAttachment.is_active.is_(True),
        )
        .order_by(DocumentAttachment.uploaded_at.desc(), DocumentAttachment.id.desc())
        .all()
    )


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    storage: LocalFileStorage = Depends(get_document_storage),
):
    attachment = db.get(DocumentAttachment, attachment_id)
    if not attachment or not attachment.is_active:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not storage.exists(attachment.storage_path):
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return StreamingResponse(
        stream_file(storage.open(attachment.storage_path)),
        media_type=attachment.mime_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition(attachment.original_file_name)},
    )


@router.delete("/{attachment_id}", response_model=DocumentAttachmentResponse)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    attachment = db.get(DocumentAttachment, attachment_id)
    if not attachment or not attachment.is_active:
        raise HTTPException(status_code=404, detail="Attachment not found")
    attachment.is_active = False
    attachment.deleted_by_id = user.id
    attachment.deleted_at = datetime.now(timezone.utc)
    ActivityService.log(
        db=db,
        user=user,
        action="DELETE_ATTACHMENT",
        entity_type=attachment.entity_type,
        entity_id=attachment.entity_id,
        summary=f"Soft-deleted supporting document {attachment.original_file_name}",
        details={"attachment_id": attachment.id},
    )
    db.commit()
    db.refresh(attachment)
    return attachment

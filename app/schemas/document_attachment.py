from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DocumentAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    attachment_type: str
    document_number: str | None
    document_date: date | None
    original_file_name: str
    storage_provider: str
    mime_type: str | None
    file_size: int
    checksum_sha256: str
    description: str | None
    source_type: str
    uploaded_by_id: int | None
    uploaded_at: datetime
    is_active: bool
    deleted_by_id: int | None
    deleted_at: datetime | None

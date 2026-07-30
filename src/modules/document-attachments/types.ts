export type AttachmentEntityType =
  | "PURCHASE_REQUISITION"
  | "PURCHASE_ORDER"
  | "GOODS_RECEIPT"
  | "PURCHASING_DOCUMENT";

export type AttachmentSourceType = "LIVE" | "HISTORICAL_IMPORT";

export interface DocumentAttachment {
  id: number;
  entity_type: AttachmentEntityType;
  entity_id: number;
  attachment_type: string;
  document_number: string | null;
  document_date: string | null;
  original_file_name: string;
  storage_provider: string;
  mime_type: string | null;
  file_size: number;
  checksum_sha256: string;
  description: string | null;
  source_type: AttachmentSourceType;
  uploaded_by_id: number | null;
  uploaded_at: string;
  is_active: boolean;
  deleted_by_id: number | null;
  deleted_at: string | null;
}

export interface AttachmentUploadInput {
  entityType: AttachmentEntityType;
  entityId: number;
  file: File;
  attachmentType: string;
  documentNumber?: string;
  documentDate?: string;
  description?: string;
  sourceType: AttachmentSourceType;
}

export interface AuditEvent {
  id: number;
  occurred_at: string;
  actor_user_id: number | null;
  actor_name: string | null;
  role_names: string[];
  department_name: string | null;
  location_name: string | null;
  action: string;
  entity_type: string;
  entity_id: number;
  summary: string;
  document_type: string | null;
  document_number: string | null;
  document_status: string | null;
  reference_document: string | null;
  approval_level: number | null;
  approval_step: number | null;
  details: unknown;
  before_data: unknown;
  after_data: unknown;
  source: string | null;
  import_batch_id: number | null;
}

export interface PaginatedReportResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface AuditReportParams {
  page: number;
  pageSize: number;
  documentNumber: string;
  documentType: string;
  action: string;
  actor: string;
  dateFrom: string;
  dateTo: string;
}

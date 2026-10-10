import api from "@/api/client";

export type JournalLine = {
  id: number;
  line_number?: number;
  account_id: number;
  account_code: string;
  account_name: string;
  description?: string | null;
  debit: number;
  credit: number;
  business_unit_id?: number | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  supplier_id?: number | null;
};

export type Journal = {
  id: number;
  journal_number: string;
  journal_date: string;
  description?: string | null;
  reference_type: string;
  reference_id: number;
  reference_number?: string | null;
  status: string;
  business_unit_id?: number | null;
  business_unit_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  created_by_name?: string | null;
  posted_by_name?: string | null;
  total_debit: number;
  total_credit: number;
  difference: number;
  allowed_actions: Record<string, boolean>;
  lines: JournalLine[];
};

export type JournalCreatePayload = {
  copied_from_journal_id?: number;
  posting_date: string;
  document_type: string;
  document_number: string;
  reference_type: string;
  reference_id: number;
  description?: string;
  business_unit_id: number;
  department_id?: number | null;
  location_id?: number | null;
  lines: Array<{
    account_id: number;
    debit: number;
    credit: number;
    description?: string;
    business_unit_id?: number | null;
    department_id?: number | null;
    location_id?: number | null;
    supplier_id?: number | null;
  }>;
};

export type JournalUpdatePayload = {
  posting_date?: string;
  location_id?: number | null;
  description?: string | null;
  lines?: Array<{
    account_id: number;
    debit: number;
    credit: number;
    description?: string;
    business_unit_id?: number | null;
    department_id?: number | null;
    location_id?: number | null;
    supplier_id?: number | null;
  }>;
};

export const listJournals = async (params: any = {}) => (await api.get("/journal-entries", { params })).data;
export const getJournal = async (id: number) => (await api.get<Journal>(`/journal-entries/${id}`)).data;
export const createJournal = async (payload: JournalCreatePayload) => (await api.post<Journal>("/journal-entries", payload)).data;
export const updateJournal = async (id: number, payload: JournalUpdatePayload) => (await api.patch<Journal>(`/journal-entries/${id}`, payload)).data;
export const journalAction = async (id: number, action: string) => (await api.post<Journal>(`/journal-entries/${id}/${action}`)).data;

export type CurrentPeriodPreview = {
  period_id: number;
  period_name: string;
  start_date: string;
  end_date: string;
  draft_count: number;
  posted_count: number;
};

export const getCurrentPeriodPreview = async () =>
  (await api.get<CurrentPeriodPreview>("/journal-entries/bulk/current-period-preview")).data;

export const bulkJournalAction = async (journalIds: number[], action: "post" | "unpost") =>
  (await api.post<{ processed: number; status: string; journal_ids: number[] }>(
    `/journal-entries/bulk/${action}`,
    { journal_ids: journalIds },
  )).data;

export const recreateCurrentPeriod = async () =>
  (await api.post<{
    period_id: number;
    period_name: string;
    journals_recreated: number;
    ledger_rows_recreated: number;
  }>("/journal-entries/bulk/recreate-current-period")).data;

export type JournalImportJob = {
  id: number;
  batch_number: string;
  batch_name: string;
  status: string;
  original_file_name?: string | null;
  total_rows: number;
  valid_rows: number;
  warning_rows: number;
  error_rows: number;
  imported_rows: number;
  failed_rows: number;
  total_documents: number;
  success_count: number;
  failed_count: number;
  period_from?: string | null;
  period_to?: string | null;
  worker_error_message?: string | null;
  created_at?: string | null;
  validated_at?: string | null;
  imported_at?: string | null;
};

export type JournalImportPreviewRow = {
  journal_group: string;
  document_number?: string | null;
  posting_date?: string | null;
  description?: string | null;
  location?: string | null;
  line_count: number;
  debit: number;
  credit: number;
  difference: number;
  status: "VALID" | "ERROR";
  errors: string[];
};

export type JournalImportErrorRow = {
  row_number: number;
  sheet_name?: string | null;
  document_number?: string | null;
  journal_group?: string | null;
  status: string;
  errors: string[];
  warnings: string[];
  data?: Record<string, unknown>;
};

export const createJournalImport = async (batch_name: string) =>
  (await api.post<JournalImportJob>("/journal-imports", { batch_name })).data;

export const getJournalImportUploadUrl = async (id: number, filename: string, content_type: string) =>
  (await api.post<{ upload_url: string; content_type: string }>(
    `/journal-imports/${id}/upload-url`,
    { filename, content_type },
  )).data;

export const completeJournalImportUpload = async (id: number) =>
  (await api.post<JournalImportJob>(`/journal-imports/${id}/complete`)).data;

export const startJournalImport = async (id: number) =>
  (await api.post<JournalImportJob>(`/journal-imports/${id}/start`)).data;

export const confirmJournalImport = async (id: number, postValid = false) =>
  (await api.post<JournalImportJob>(`/journal-imports/${id}/confirm`, { post_valid: postValid })).data;

export const getJournalImport = async (id: number) =>
  (await api.get<JournalImportJob>(`/journal-imports/${id}`)).data;

export const getJournalImportPreview = async (id: number) =>
  (await api.get<{ job_id: number; status: string; journals: JournalImportPreviewRow[] }>(
    `/journal-imports/${id}/preview`,
  )).data;

export const getJournalImportErrors = async (id: number) =>
  (await api.get<{ job_id: number; rows: JournalImportErrorRow[] }>(
    `/journal-imports/${id}/errors`,
  )).data;

const downloadBase64File = (data: {
  filename: string;
  content_base64: string;
  content_type: string;
}) => {
  const binary = atob(data.content_base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  const blob = new Blob([bytes], { type: data.content_type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = data.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

export const downloadJournalImportTemplate = async () => {
  const response = await api.get<{
    filename: string;
    content_base64: string;
    content_type: string;
  }>("/journal-imports/template");
  downloadBase64File(response.data);
};

export const downloadJournalImportCorrections = async (id: number) => {
  const response = await api.get<{
    filename: string;
    content_base64: string;
    content_type: string;
  }>(`/journal-imports/${id}/correction-file`);
  downloadBase64File(response.data);
};

export const uploadJournalImport = async (file: File, batchName: string) => {
  const job = await createJournalImport(batchName);
  const contentType = file.type || (file.name.toLowerCase().endsWith(".csv")
    ? "text/csv"
    : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  const upload = await getJournalImportUploadUrl(job.id, file.name, contentType);
  const response = await fetch(upload.upload_url, {
    method: "PUT",
    headers: { "Content-Type": upload.content_type },
    body: file,
  });
  if (!response.ok) throw new Error(`S3 upload failed: HTTP ${response.status}`);
  await completeJournalImportUpload(job.id);
  return startJournalImport(job.id);
};

export type JournalScope = {
  units: { id: number; name: string; code: string }[];
  locations: { id: number; name: string; code: string; business_unit_id: number | null }[];
  default_business_unit_id: number | null;
  default_location_id: number | null;
  location_locked: boolean;
};
export const getJournalScope = async () => (await api.get<JournalScope>("/journal-entries/scope")).data;
export const getJournalCopyTemplate = async (id: number) => (await api.get<{
  copied_from_journal_id: number; source_number: string; description: string | null;
  business_unit_id: number | null; location_id: number | null; department_id: number | null;
  lines: JournalLine[];
}>(`/journal-entries/${id}/copy-template`)).data;

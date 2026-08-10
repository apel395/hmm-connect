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
  }>;
};

export type JournalUpdatePayload = {
  posting_date?: string;
  description?: string | null;
  lines?: Array<{
    account_id: number;
    debit: number;
    credit: number;
    description?: string;
    business_unit_id?: number | null;
    department_id?: number | null;
    location_id?: number | null;
  }>;
};

export const listJournals = async (params: any = {}) => (await api.get("/journal-entries", { params })).data;
export const getJournal = async (id: number) => (await api.get<Journal>(`/journal-entries/${id}`)).data;
export const createJournal = async (payload: JournalCreatePayload) => (await api.post<Journal>("/journal-entries", payload)).data;
export const updateJournal = async (id: number, payload: JournalUpdatePayload) => (await api.patch<Journal>(`/journal-entries/${id}`, payload)).data;
export const journalAction = async (id: number, action: string) => (await api.post<Journal>(`/journal-entries/${id}/${action}`)).data;

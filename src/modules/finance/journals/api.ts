import api from "@/api/client";
export type JournalLine={id:number;line_number?:number;account_id:number;account_code:string;account_name:string;description?:string|null;debit:number;credit:number;department_name?:string|null;location_name?:string|null};
export type Journal={id:number;journal_number:string;journal_date:string;description?:string|null;reference_type:string;reference_id:number;reference_number?:string|null;status:string;created_by_name?:string|null;posted_by_name?:string|null;total_debit:number;total_credit:number;difference:number;allowed_actions:Record<string,boolean>;lines:JournalLine[]};
export const listJournals=async(params:any={})=>(await api.get("/journal-entries",{params})).data;
export const getJournal=async(id:number)=>(await api.get<Journal>(`/journal-entries/${id}`)).data;
export const journalAction=async(id:number,action:string)=>(await api.post<Journal>(`/journal-entries/${id}/${action}`)).data;

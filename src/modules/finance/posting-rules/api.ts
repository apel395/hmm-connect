import api from "@/api/client";

export type PostingRule={
  id:number;
  event_type:string;
  business_unit_id?:number|null;
  business_unit_name?:string|null;
  location_id?:number|null;
  location_name?:string|null;
  debit_account_id:number;
  debit_account_code:string;
  debit_account_name:string;
  credit_account_id:number;
  credit_account_code:string;
  credit_account_name:string;
  input_vat_account_id?:number|null;
  input_vat_account_code?:string|null;
  input_vat_account_name?:string|null;
  description?:string|null;
  is_active:boolean;
};

export type PostingRulePayload={
  event_type:string;
  business_unit_id?:number|null;
  location_id?:number|null;
  debit_account_id:number;
  credit_account_id:number;
  input_vat_account_id?:number|null;
  description?:string|null;
  is_active:boolean;
};

export const listRules=async()=> (await api.get<PostingRule[]>("/accounting/posting-rules")).data;
export const createRule=async(p:PostingRulePayload)=>(await api.post<PostingRule>("/accounting/posting-rules",p)).data;
export const updateRule=async(id:number,p:Partial<PostingRulePayload>)=>(await api.patch<PostingRule>(`/accounting/posting-rules/${id}`,p)).data;
export const toggleRule=async(id:number,active:boolean)=>(await api.patch<PostingRule>(`/accounting/posting-rules/${id}/${active?"restore":"archive"}`)).data;

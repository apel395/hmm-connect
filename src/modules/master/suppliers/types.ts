export interface SupplierPIC {
  id: number;
  pic_name: string;
  phone: string | null;
  unit: string | null;
  item: string | null;
}

export interface Supplier {
  id: number;
  code: string;
  name: string;
  address: string;
  bank_name: string;
  bank_account_number: string;
  bank_account_name: string;
  is_pkp: boolean;
  npwp?: string | null;
  nitku?: string | null;
  tax_registration_name?: string | null;
  is_active: boolean;
  rows?: SupplierPIC[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SupplierPICPayload {
  id?: number;
  pic_name: string;
  phone: string | null;
  unit: string | null;
  item: string | null;
}

export interface SupplierPayload {
  code: string;
  name: string;
  address: string;
  bank_name: string;
  bank_account_number: string;
  bank_account_name: string;
  is_pkp: boolean;
  npwp: string | null;
  nitku: string | null;
  tax_registration_name: string | null;
  is_active: boolean;
  rows: SupplierPICPayload[];
}

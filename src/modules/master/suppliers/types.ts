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

  is_active: boolean;

  rows: SupplierPIC[];
}
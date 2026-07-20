import api from "../../api/client";

export interface SupplierRow {
  id: number;
  pic_name: string | null;
  phone: string | null;
  unit: string | null;
  item: string | null;
}

export interface Supplier {
  id: number;
  code: string;
  name: string;
  address: string | null;
  bank_name: string | null;
  bank_account_number: string | null;
  bank_account_name: string | null;
  is_active: boolean;
  rows: SupplierRow[];
}

export interface CreateSupplierRowRequest {
  pic_name?: string;
  phone?: string;
  unit?: string;
  item?: string;
}

export interface UpdateSupplierRequest {
  code: string;
  name: string;
  address?: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_account_name?: string;
  rows: CreateSupplierRowRequest[];
}

export interface CreateSupplierRequest {
  code: string;
  name: string;
  address?: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_account_name?: string;
  rows: CreateSupplierRowRequest[];
}

export async function getSuppliers(): Promise<Supplier[]> {
  const response = await api.get<Supplier[]>("/suppliers");

  return response.data;
}

export async function createSupplier(
  data: CreateSupplierRequest,
): Promise<Supplier> {
  const response = await api.post<Supplier>(
    "/suppliers",
    data,
  );

  return response.data;
}


export async function updateSupplier(
  supplierId: number,
  data: UpdateSupplierRequest,
): Promise<Supplier> {
  const response = await api.patch<Supplier>(
    `/suppliers/${supplierId}`,
    data,
  );

  return response.data;
}

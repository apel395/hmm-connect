export interface SupplierProduct {
  id: number;

  product_id: number;

  product_name: string;

  purchase_uom: string;

  last_price: number;

  lead_time: number;

  preferred: boolean;

  is_active: boolean;
}

export interface SupplierProductPayload {
  product_id: number;

  last_price: number;

  lead_time: number;

  preferred: boolean;
}

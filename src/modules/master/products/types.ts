export type TaxCategory = "STANDARD" | "EXEMPT" | "NON_VAT" | "SPECIAL" | "REVIEW_REQUIRED";

export interface Product {
  id: number;
  code: string;
  name: string;
  group_code: string;
  group_name: string;
  subgroup_code: string;
  subgroup_name: string;
  uom: string;
  usage_uom: string;
  conversion: string | number;
  tax_category: TaxCategory;
  is_taxable: boolean;
  tax_rate: string | number;
  tax_reason?: string | null;
  tax_reference?: string | null;
  minimum_stock: string | number;
  is_market_item: boolean;
  is_active: boolean;
}

export interface ProductCreateRequest {
  name: string;
  group_code: string;
  group_name: string;
  subgroup_code: string;
  subgroup_name: string;
  uom: string;
  usage_uom: string;
  conversion: number;
  tax_category: TaxCategory;
  is_taxable: boolean;
  tax_rate: number;
  tax_reason?: string | null;
  tax_reference?: string | null;
  minimum_stock: number;
  is_market_item: boolean;
}

export type ProductUpdateRequest = ProductCreateRequest;

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
}

export type ProductUpdateRequest =
  ProductCreateRequest;
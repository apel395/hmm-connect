import api from "../../api/client";

export interface Product {
  id: number;
  code: string;
  name: string;
  description: string | null;
  uom: string;
  cost_price: number;
  selling_price: number;
  is_active: boolean;
}

export interface CreateProductRequest {
  code: string;
  name: string;
  description?: string;
  uom: string;
  cost_price: number;
  selling_price: number;
}

export async function getProducts(): Promise<Product[]> {
  const response = await api.get<Product[]>("/products");

  return response.data;
}

export async function createProduct(
  data: CreateProductRequest,
): Promise<Product> {
  const response = await api.post<Product>(
    "/products",
    data,
  );

  return response.data;
}
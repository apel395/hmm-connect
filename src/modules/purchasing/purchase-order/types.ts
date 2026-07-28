export interface PurchaseOrderItem {

  id: number;


  purchase_order_id?: number;


  purchase_requisition_item_id?: number | null;


  product_id: number;


  product_code?: string;


  product_name: string;


  quantity: number;


  received_quantity: number;


  remaining_quantity?: number;


  unit_price: number;


  total_price: number;

}



export interface PurchaseOrder {


  id: number;


  po_number: string;



  supplier_id: number;


  supplier_name: string;



  purchase_requisition_id?: number | null;


  purchase_requisition_ids?: number[];



  status:
    | "DRAFT"
    | "PENDING_APPROVAL"
    | "APPROVED"
    | "PARTIALLY_RECEIVED"
    | "RECEIVED"
    | "REJECTED";



  order_date: string;


  expected_date: string;


  expiry_date?: string | null;



  receipt_tolerance_percent?: number;



  notes?: string | null;



  total_amount: number;



  items: PurchaseOrderItem[];

}
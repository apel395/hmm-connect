export interface PurchaseRequisition {
  id:number;
  pr_number:string;
  request_date:string;
  required_date:string;
  warehouse_id:number;
  business_unit_id?:number|null;
  business_unit_name?:string|null;
  department_id:number;
  department_name?:string|null;
  location_id?:number|null;
  location_name?:string|null;
  requester_name:string;
  priority:string;
  status:string;
  notes:string;
  subtotal:number;
  tax_amount:number;
  total_amount:number;
  items:PurchaseRequisitionItem[];
  allowed_actions?: {
    can_edit:boolean; can_submit:boolean; can_approve:boolean; can_reject:boolean;
    can_print:boolean; can_view_history:boolean; can_manage_attachments:boolean;
  };
  approval_history?: Array<{ level:number; name:string; approver_role:string; location_name?:string|null; status:string; approver_name?:string|null; decided_at?:string|null; comment?:string|null }>;
  activity_history?: import("../components/DocumentActivity").DocumentActivityItem[];
  generated_purchase_orders?: Array<{ id:number; document_number:string; status:string }>;
}

export interface PurchaseRequisitionItem {
  id:number;
  product_id:number;
  product_code:string;
  product_name:string;
  uom:string;
  quantity:number;
  estimated_price:number;
  total_price:number;
  is_taxable:boolean;
  tax_rate:number;
  tax_amount:number;
  line_total?:number;
  remark?:string;
}

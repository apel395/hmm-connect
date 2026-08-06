export interface PurchaseRequisition{

id:number;

pr_number:string;

request_date:string;

required_date:string;

warehouse_id:number;

department_id:number;

requester_name:string;

priority:string;

status:string;

notes:string;

total_amount:number;

items:PurchaseRequisitionItem[];

allowed_actions?: {
  can_edit:boolean; can_submit:boolean; can_approve:boolean; can_reject:boolean;
  can_print:boolean; can_view_history:boolean; can_manage_attachments:boolean;
};

approval_history?: Array<{ level:number; name:string; approver_role:string; status:string; approver_name?:string|null; decided_at?:string|null; comment?:string|null }>;
activity_history?: import("../components/DocumentActivity").DocumentActivityItem[];
generated_purchase_orders?: Array<{ id:number; document_number:string; status:string }>;

}

export interface PurchaseRequisitionItem{

id:number;

product_id:number;

product_code:string;

product_name:string;

uom:string;

quantity:number;

estimated_price:number;

total_price:number;

remark?:string;

}

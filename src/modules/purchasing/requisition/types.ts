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

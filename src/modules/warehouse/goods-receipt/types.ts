export interface GoodsReceipt{

id:number;

receipt_number:string;

purchase_order_id:number;

po_number:string;

supplier_name:string;

received_at:string;

warehouse_name:string;

status:string;

items:GoodsReceiptItem[];

}

export interface GoodsReceiptItem{

id:number;

purchase_order_item_id:number;

product_code:string;

product_name:string;

ordered_quantity:number;

received_quantity:number;

accepted_quantity:number;

rejected_quantity:number;

uom:string;

}

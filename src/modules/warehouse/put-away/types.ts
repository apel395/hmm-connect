export interface PutAway{

id:number;

putaway_number:string;

receipt_number:string;

warehouse_name:string;

status:string;

items:PutAwayItem[];

}

export interface PutAwayItem{

id:number;

product_code:string;

product_name:string;

quantity:number;

from_location:string;

to_location:string;

}

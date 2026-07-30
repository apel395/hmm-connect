export interface Inventory{

id:number;

product_code:string;

product_name:string;

warehouse_name:string;

quantity:number;

reserved_quantity:number;

available_quantity:number;

average_cost:number;

inventory_account:string;

minimum_stock?:number;

}

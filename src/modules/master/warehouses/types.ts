export interface Warehouse { id:number; code:string; name:string; address?:string|null; location_id?:number|null; is_active:boolean }
export interface WarehousePayload { code:string; name:string; address?:string|null; location_id?:number|null }
export interface WarehouseUpdatePayload { name?:string; address?:string|null; location_id?:number|null; is_active?:boolean }

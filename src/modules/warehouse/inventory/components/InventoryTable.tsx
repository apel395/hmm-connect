import{

Table,
THead,
TBody,
TR,
TH,
TD,

}from"@/components/ui/Table";

export default function InventoryTable({

rows,

}:any){

return(

<Table>

<THead>

<TR>

<TH>Code</TH>

<TH>Name</TH>

<TH>Warehouse</TH>

<TH>Qty</TH>

<TH>Reserved</TH>

<TH>Available</TH>

<TH>Average Cost</TH>

<TH>COA</TH>

</TR>

</THead>

<TBody>

{

rows.map((row:any)=>(

<TR key={row.id}>

<TD>{row.product_code}</TD>

<TD>{row.product_name}</TD>

<TD>{row.warehouse_name}</TD>

<TD>{row.quantity}</TD>

<TD>{row.reserved_quantity}</TD>

<TD>{row.available_quantity}</TD>

<TD>{row.average_cost}</TD>

<TD>{row.inventory_account}</TD>

</TR>

))

}

</TBody>

</Table>

);

}

import{

Table,
THead,
TBody,
TR,
TH,
TD,

}from"@/components/ui/Table";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";

export default function GoodsReceiptTable({

rows,

}:any){

return(

<Table>

<THead>

<TR>

<TH>Receipt</TH>

<TH>PO</TH>

<TH>Supplier</TH>

<TH>Date</TH>

<TH>Status</TH>

<TH></TH>

</TR>

</THead>

<TBody>

{

rows.map((row:any)=>(

<TR key={row.id}>

<TD>{row.receipt_number}</TD>

<TD>{row.po_number}</TD>

<TD>{row.supplier_name}</TD>

<TD>{row.received_at}</TD>

<TD>

<Badge>

{row.status}

</Badge>

</TD>

<TD>

<Button>

Open

</Button>

</TD>

</TR>

))

}

</TBody>

</Table>

);

}

import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";

import{

useInventoryMovements,

}from"../useInventoryMovement";

export default function InventoryMovementPage(){

const{

data=[],
isLoading,

}=useInventoryMovements();

if(isLoading)return<Loading/>;

return(

<div className="space-y-6">

<PageHeader

title="Inventory Movement"

description="Complete warehouse stock history"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Date</th>

<th>Movement</th>

<th>Product</th>

<th>Type</th>

<th>Reference</th>

<th>Qty</th>

<th>Balance</th>

</tr>

</thead>

<tbody>

{

data.map((row:any)=>(

<tr key={row.id}>

<td>{row.movement_date}</td>

<td>{row.movement_number}</td>

<td>{row.product_name}</td>

<td>{row.movement_type}</td>

<td>{row.reference_number}</td>

<td>{row.quantity}</td>

<td>{row.balance}</td>

</tr>

))

}

</tbody>

</table>

</Card>

</div>

);

}

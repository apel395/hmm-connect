import Card from "@/components/ui/Card";
import PageHeader from "@/components/common/PageHeader";

export default function InventoryAccountMapping(){

return(

<div className="space-y-6">

<PageHeader

title="Inventory COA Mapping"

description="Product accounting configuration"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Product Group</th>

<th>Inventory Account</th>

<th>COGS Account</th>

<th>Purchase Variance</th>

<th>Inventory Adjustment</th>

</tr>

</thead>

<tbody>

</tbody>

</table>

</Card>

</div>

);

}

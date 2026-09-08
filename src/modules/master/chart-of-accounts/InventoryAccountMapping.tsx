import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";

export default function InventoryAccountMapping(){

return(

<div className="space-y-6">

<PageHeader

 actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Inventory COA Mapping"

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

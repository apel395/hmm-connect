import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";

export default function StockCardPage(){

return(

<div className="space-y-6">

<PageHeader

title="Stock Card"

description="Complete inventory transaction history"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Date</th>

<th>Reference</th>

<th>IN</th>

<th>OUT</th>

<th>Balance</th>

</tr>

</thead>

<tbody>

</tbody>

</table>

</Card>

</div>

);

}

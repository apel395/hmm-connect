import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function TaxPage(){

return(

<div className="space-y-6">

<PageHeader

title="Tax"

description="Tax Configuration"

actions={<Button>New Tax</Button>}

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Code</th>

<th>Name</th>

<th>Rate</th>

<th>Purchase</th>

<th>Sales</th>

</tr>

</thead>

<tbody>

</tbody>

</table>

</Card>

</div>

);

}

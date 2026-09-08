import { Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function CurrencyPage(){

return(

<div className="space-y-6">

<PageHeader

title="Currency"

description="Currency Master"

actions={<>
<Button>New Currency</Button>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Code</th>

<th>Name</th>

<th>Symbol</th>

<th>Rate</th>

<th>Base</th>

</tr>

</thead>

<tbody>

</tbody>

</table>

</Card>

</div>

);

}

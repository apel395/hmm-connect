import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";

export default function SettingPage(){

return(

<div className="space-y-6">

<PageHeader

title="Settings"

description="Application Settings"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Key</th>

<th>Value</th>

</tr>

</thead>

<tbody>

<tr>

<td>Company Name</td>

<td></td>

</tr>

<tr>

<td>Default Warehouse</td>

<td></td>

</tr>

<tr>

<td>Default Currency</td>

<td></td>

</tr>

<tr>

<td>Timezone</td>

<td></td>

</tr>

</tbody>

</table>

</Card>

</div>

);

}

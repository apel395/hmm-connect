import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";

export default function AuditLogPage(){

return(

<div className="space-y-6">

<PageHeader

title="Audit Log"

description="System Activity"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Time</th>

<th>User</th>

<th>Module</th>

<th>Action</th>

<th>Description</th>

</tr>

</thead>

<tbody>

</tbody>

</table>

</Card>

</div>

);

}

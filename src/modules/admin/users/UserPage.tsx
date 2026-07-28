import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function UserPage(){

return(

<div className="space-y-6">

<PageHeader

title="Users"

description="System Users"

actions={<Button>New User</Button>}

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Name</th>

<th>Email</th>

<th>Role</th>

<th>Status</th>

</tr>

</thead>

<tbody>

</tbody>

</table>

</Card>

</div>

);

}

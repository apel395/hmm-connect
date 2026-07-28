import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";

export default function NotificationPage(){

return(

<div className="space-y-6">

<PageHeader

title="Notifications"

description="System Notification"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Date</th>

<th>Message</th>

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

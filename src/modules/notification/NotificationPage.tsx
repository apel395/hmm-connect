import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function NotificationPage(){

return(

<div className="space-y-6">

<PageHeader

 actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Notifications"

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

<tr>

<td colSpan={3} className="px-4 py-12 text-center text-sm text-slate-500">

No notifications yet.

</td>

</tr>

</tbody>

</table>

</Card>

</div>

);

}

import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function ProfilePage(){

return(

<div className="space-y-6">

<PageHeader

 actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="My Profile"

description="Account Information"

/>

<Card>

<div className="space-y-4">

<input
className="w-full rounded border p-2"
placeholder="Full Name"
/>

<input
className="w-full rounded border p-2"
placeholder="Email"
/>

<input
className="w-full rounded border p-2"
placeholder="Phone"
/>

<Button>

Update Profile

</Button>

</div>

</Card>

</div>

);

}

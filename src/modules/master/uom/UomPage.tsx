import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function UomPage(){

return(

<div className="space-y-6">

<PageHeader

 actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Unit of Measure"

description="Manage UOM"

/>

<Card>

UOM Management

</Card>

</div>

);

}

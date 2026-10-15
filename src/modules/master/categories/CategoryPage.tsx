import DataWorkspace from "@/components/workspace/DataWorkspace";
import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function CategoryPage(){

return(

<DataWorkspace area="Master data" >

<PageHeader

 actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Product Categories"

description="Manage product groups"

/>

<Card className="workspace-data workspace-table-scroll">

Category Management

</Card>

</DataWorkspace>

);

}

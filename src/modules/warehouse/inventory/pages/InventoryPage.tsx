import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";

import InventoryTable from "../components/InventoryTable";

import{

useInventory,

}from"../useInventory";

export default function InventoryPage(){

const{

data=[],

isLoading,

}=useInventory();

return(

<div className="space-y-6">

<PageHeader

title="Inventory"

description="Current Stock"

/>

<Card>

{

isLoading

?

<Loading/>

:

<InventoryTable

rows={data}

/>

}

</Card>

</div>

);

}

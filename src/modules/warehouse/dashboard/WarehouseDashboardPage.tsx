import Card from "@/components/ui/Card";
import PageHeader from "@/components/common/PageHeader";

export default function WarehouseDashboardPage(){

const cards=[

["Pending Receipt",18],
["Pending Put Away",7],
["Available SKU",1256],
["Low Stock",34],
["Out Of Stock",11],
["Inventory Value","2,815,000"],

];

return(

<div className="space-y-6">

<PageHeader

title="Warehouse Dashboard"

description="Warehouse Overview"

/>

<div className="grid grid-cols-3 gap-6">

{

cards.map(([title,value])=>(

<Card key={title}>

<div className="text-sm text-slate-500">

{title}

</div>

<div className="mt-1 text-2xl font-bold">

{value}

</div>

</Card>

))

}

</div>

</div>

);

}

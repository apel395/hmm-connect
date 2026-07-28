import Card from "@/components/ui/Card";
import PageHeader from "@/components/common/PageHeader";

export default function DashboardPage(){

const cards=[

["Purchase Requisition",18],
["Purchase Order",12],
["Pending Receipt",6],
["Put Away",4],
["Inventory Item",1245],
["Low Stock",23],

];

return(

<div className="space-y-6">

<PageHeader

title="Dashboard"

description="ERP Overview"

/>

<div className="grid grid-cols-3 gap-6">

{

cards.map(([title,value])=>(

<Card key={title}>

<div className="text-sm text-slate-500">

{title}

</div>

<div className="mt-2 text-3xl font-bold">

{value}

</div>

</Card>

))

}

</div>

</div>

);

}

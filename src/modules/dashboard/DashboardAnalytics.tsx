import KpiCard from "@/components/dashboard/KpiCard";
import DashboardLineChart from "@/components/dashboard/LineChart";
import DashboardPie from "@/components/dashboard/PieChart";

const purchase=[

{month:"Jan",value:12},
{month:"Feb",value:18},
{month:"Mar",value:15},
{month:"Apr",value:24},
{month:"May",value:19},
{month:"Jun",value:30},

];

const inventory=[

{name:"Available",value:80},
{name:"Reserved",value:15},
{name:"Damaged",value:5},

];

export default function DashboardAnalytics(){

return(

<div className="space-y-6">

<div className="grid grid-cols-4 gap-6">

<KpiCard

title="Inventory Value"

value="$2,815,000"

/>

<KpiCard

title="Purchase Order"

value="142"

/>

<KpiCard

title="Supplier"

value="86"

/>

<KpiCard

title="Low Stock"

value="15"

/>

</div>

<DashboardLineChart

data={purchase}

/>

<DashboardPie

data={inventory}

/>

</div>

);

}

import Card from "@/components/ui/Card";

interface Props{

title:string;

value:string|number;

change?:string;

}

export default function KpiCard({

title,

value,

change,

}:Props){

return(

<Card>

<div className="text-sm text-slate-500">

{title}

</div>

<div className="mt-3 text-3xl font-bold">

{value}

</div>

{

change&&(

<div className="mt-2 text-sm text-green-600">

{change}

</div>

)

}

</Card>

);

}

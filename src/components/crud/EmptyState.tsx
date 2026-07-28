export default function EmptyState({

title,

}:{

title:string;

}){

return(

<div className="flex h-56 items-center justify-center rounded border">

<div className="text-center">

<h3 className="text-xl font-semibold">

{title}

</h3>

<p className="mt-2 text-slate-500">

No data available.

</p>

</div>

</div>

);

}

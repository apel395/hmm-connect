export default function TableSkeleton(){

return(

<div className="animate-pulse space-y-3">

{

Array.from({length:8}).map((_,i)=>(

<div

key={i}

className="h-10 rounded bg-slate-200"

/>

))

}

</div>

);

}

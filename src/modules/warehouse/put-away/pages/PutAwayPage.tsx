import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";

import{

usePutAway,
useCompletePutAway,

}from"../usePutAway";

export default function PutAwayPage(){

const{

data=[],
isLoading,

}=usePutAway();

const complete=
useCompletePutAway();

if(isLoading)return<Loading/>;

return(

<div className="space-y-6">

<PageHeader

 actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Put Away"

description="Move received stock into warehouse locations"

/>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>No</th>

<th>Receipt</th>

<th>Warehouse</th>

<th>Status</th>

<th></th>

</tr>

</thead>

<tbody>

{

data.map((row:any)=>(

<tr key={row.id}>

<td>{row.putaway_number}</td>

<td>{row.receipt_number}</td>

<td>{row.warehouse_name}</td>

<td>{row.status}</td>

<td>

<Button

onClick={()=>

complete.mutate({

id:row.id,

})

}

>

Complete

</Button>

</td>

</tr>

))

}

</tbody>

</table>

</Card>

</div>

);

}

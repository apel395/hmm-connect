import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { inventoryDocumentReport } from "@/modules/warehouse/inventory/print/reports";
import InventoryReportHeading from "@/components/print/InventoryReportHeading";
import PageHeader from "@/components/common/PageHeader";
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

<div className="inventory-print-report space-y-6">
<InventoryReportHeading title="Put Away" context={"Received stock awaiting warehouse placement"} rows={data.length} total={data.length}/>

<PageHeader

 actions={<InventoryPrintButton loadReport={() => inventoryDocumentReport("putaway",{}, "Received stock awaiting placement")}/>} title="Put Away"

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

<th className="print:hidden"></th>

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

<td className="print:hidden">

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

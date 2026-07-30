import { useParams } from "react-router-dom";

import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import PageHeader from "@/components/common/PageHeader";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";

import {
useGoodsReceipt,
useCompleteReceipt,
} from "../hooks/useGoodsReceipts";

export default function GoodsReceiptDetailPage(){

const{id}=useParams();

const{
data,
isLoading,
}=useGoodsReceipt(Number(id));

const complete=
useCompleteReceipt();

if(isLoading)return<Loading/>;

if(!data)return null;

return(

<div className="space-y-6">

<PageHeader

title={data.receipt_number}

description="Goods Receipt"

/>

<Card>

<div className="grid grid-cols-4 gap-6">

<div>

<div className="text-xs text-slate-500">

Purchase Order

</div>

<div>

{data.po_number}

</div>

</div>

<div>

<div className="text-xs text-slate-500">

Supplier

</div>

<div>

{data.supplier_name}

</div>

</div>

<div>

<div className="text-xs text-slate-500">

Warehouse

</div>

<div>

{data.warehouse_name}

</div>

</div>

<div>

<div className="text-xs text-slate-500">

Received At

</div>

<div>

{data.received_at}

</div>

</div>

</div>

</Card>

<Card>

<table className="min-w-full">

<thead>

<tr>

<th>Product</th>

<th>Ordered</th>

<th>Receive</th>

<th>Accepted</th>

<th>Rejected</th>

</tr>

</thead>

<tbody>

{

data.items.map((item:any)=>(

<tr key={item.id}>

<td>

{item.product_code}

{" - "}

{item.product_name}

</td>

<td>

{item.ordered_quantity}

</td>

<td>

<input

type="number"

defaultValue={item.received_quantity}

className="w-24 rounded border p-2"

/>

</td>

<td>

<input

type="number"

defaultValue={item.accepted_quantity}

className="w-24 rounded border p-2"

/>

</td>

<td>

<input

type="number"

defaultValue={item.rejected_quantity}

className="w-24 rounded border p-2"

/>

</td>

</tr>

))

}

</tbody>

</table>

<div className="mt-6 flex justify-end">

<Button

onClick={()=>

complete.mutate(data.id)

}

>

Complete Receipt

</Button>

</div>

</Card>

<DocumentAttachments
entityType="GOODS_RECEIPT"
entityId={data.id}
/>

</div>

);

}

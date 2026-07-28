import Button from "@/components/ui/Button";

import type {
  PurchaseOrder,
} from "../types";


interface Props {

  rows?: PurchaseOrder[];

  onEdit?: (
    row: PurchaseOrder
  ) => void;

  onSubmit?: (
    row: PurchaseOrder
  ) => void;

  onApprove?: (
    row: PurchaseOrder
  ) => void;

  onReject?: (
    row: PurchaseOrder
  ) => void;

  onReceive?: (
    row: PurchaseOrder
  ) => void;

}



function badgeClass(
  status:string
){

  switch(status){

    case "DRAFT":
      return "bg-slate-100 text-slate-700";


    case "PENDING_APPROVAL":
      return "bg-amber-100 text-amber-700";


    case "APPROVED":
      return "bg-green-100 text-green-700";


    case "PARTIALLY_RECEIVED":
      return "bg-blue-100 text-blue-700";


    case "RECEIVED":
      return "bg-purple-100 text-purple-700";


    case "REJECTED":
      return "bg-red-100 text-red-700";


    default:
      return "bg-slate-100 text-slate-700";

  }

}





export default function PurchaseOrderTable({

  rows=[],

  onEdit,

  onSubmit,

  onApprove,

  onReject,

  onReceive,

}:Props){


return (

<table className="w-full border-collapse">


<thead>

<tr className="border-b bg-slate-50">


<th className="p-3 text-left">
PO Number
</th>


<th className="p-3 text-left">
Supplier
</th>


<th className="p-3 text-left">
Expected
</th>


<th className="p-3 text-center">
Items
</th>


<th className="p-3 text-right">
Total
</th>


<th className="p-3 text-center">
Status
</th>


<th className="p-3 text-right">
Action
</th>


</tr>

</thead>



<tbody>


{
rows.map(row=>(


<tr

key={row.id}

className="border-b hover:bg-slate-50"

>


<td className="p-3 font-medium">

{row.po_number}

</td>



<td className="p-3">

{row.supplier_name}

</td>



<td className="p-3">

{row.expected_date}

</td>



<td className="p-3 text-center">

{row.items?.length ?? 0}

</td>



<td className="p-3 text-right">

{
Number(
row.total_amount
)
.toLocaleString(
"en-US",
{
minimumFractionDigits:2
}
)
}

</td>




<td className="p-3 text-center">


<span

className={
`rounded-full px-3 py-1 text-xs font-semibold ${
badgeClass(row.status)
}`
}

>

{
row.status.replaceAll(
"_",
" "
)
}

</span>


</td>




<td className="p-3">


<div className="flex justify-end gap-2">



{
row.status==="DRAFT"

&&

<>

<Button

size="sm"

variant="outline"

onClick={()=>
onEdit?.(row)
}

>

Edit

</Button>



<Button

size="sm"

onClick={()=>
onSubmit?.(row)
}

>

Submit

</Button>

</>

}




{
row.status==="PENDING_APPROVAL"

&&

<>

<Button

size="sm"

onClick={()=>
onApprove?.(row)
}

>

Approve

</Button>



<Button

size="sm"

variant="danger"

onClick={()=>
onReject?.(row)
}

>

Reject

</Button>


</>

}





{
(
row.status==="APPROVED"
||
row.status==="PARTIALLY_RECEIVED"
)

&&

<Button

size="sm"

onClick={()=>
onReceive?.(row)
}

>

Receive Goods

</Button>


}





{
row.status==="RECEIVED"

&&

<Button

size="sm"

variant="outline"

>

View

</Button>

}



</div>


</td>



</tr>


))

}





{
rows.length===0

&&

<tr>

<td

colSpan={7}

className="p-8 text-center text-slate-500"

>

No Purchase Orders Found

</td>

</tr>

}



</tbody>


</table>

);

}
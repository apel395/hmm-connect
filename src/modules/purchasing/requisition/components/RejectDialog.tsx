import{

useState,

}from"react";

import Dialog from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Textarea from "@/components/ui/Textarea";

export default function RejectDialog({

open,

onReject,

onClose,

}:any){

const[comment,setComment]=

useState("");

return(

<Dialog open={open}>

<h2 className="text-xl font-semibold">

Reject Document

</h2>

<Textarea

rows={5}

className="mt-4"

value={comment}

onChange={e=>

setComment(

e.target.value,

)

}

/>

<div className="mt-6 flex justify-end gap-3">

<Button

variant="outline"

onClick={onClose}

>

Cancel

</Button>

<Button

variant="danger"

onClick={()=>

onReject(comment)

}

>

Reject

</Button>

</div>

</Dialog>

);

}

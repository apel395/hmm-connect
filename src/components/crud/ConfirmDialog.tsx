import Dialog from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";

export default function ConfirmDialog({

open,

title,

message,

onConfirm,

onClose,

}:any){

return(

<Dialog open={open}>

<h2 className="text-xl font-semibold">

{title}

</h2>

<p className="mt-3">

{message}

</p>

<div className="mt-6 flex justify-end gap-3">

<Button

variant="outline"

onClick={onClose}

>

Cancel

</Button>

<Button

variant="danger"

onClick={onConfirm}

>

Confirm

</Button>

</div>

</Dialog>

);

}

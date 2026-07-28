import Button from "@/components/ui/Button";

export default function Pagination({

page,

pages,

onChange,

}:any){

return(

<div className="mt-5 flex justify-end gap-2">

<Button

disabled={page<=1}

onClick={()=>onChange(page-1)}

>

Previous

</Button>

<span className="px-3 py-2">

{page} / {pages}

</span>

<Button

disabled={page>=pages}

onClick={()=>onChange(page+1)}

>

Next

</Button>

</div>

);

}

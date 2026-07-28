import Button from "@/components/ui/Button";

export default function PrintButton(){

return(

<Button

variant="outline"

onClick={()=>window.print()}

>

Print

</Button>

);

}

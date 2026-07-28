import Button from "@/components/ui/Button";

export default function Header(){

const user=

JSON.parse(

localStorage.getItem("user")||"{}"

);

return(

<header className="flex h-16 items-center justify-between border-b bg-white px-6">

<h2 className="font-semibold">

ERP Recovery

</h2>

<div className="flex items-center gap-4">

<span>

{user.name}

</span>

<Button

variant="outline"

onClick={()=>{

localStorage.clear();

location.href="/login";

}}

>

Logout

</Button>

</div>

</header>

);

}

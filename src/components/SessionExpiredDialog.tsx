import Button from "@/components/ui/Button";

export default function SessionExpiredDialog(){

return(

<div className="fixed inset-0 flex items-center justify-center bg-black/40">

<div className="w-96 rounded-lg bg-white p-6">

<h2 className="text-xl font-semibold">

Session Expired

</h2>

<p className="mt-3">

Please login again.

</p>

<div className="mt-6 flex justify-end">

<Button

onClick={()=>{

localStorage.clear();

window.location.href="/login";

}}

>

Login

</Button>

</div>

</div>

</div>

);

}

import Button from "@/components/ui/Button";

export default function SessionExpiredDialog(){

return(

<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">

<div role="dialog" aria-modal="true" aria-labelledby="session-expired-title" className="w-96 rounded-lg bg-white p-6 shadow-2xl">

<h2 id="session-expired-title" className="text-xl font-semibold">

Session Expired

</h2>

<p className="mt-3">

Please login again.

</p>

<div className="mt-6 flex justify-end">

<Button

onClick={()=>{

["access_token","refresh_token","user","hmm-last-activity-at"].forEach((key)=>localStorage.removeItem(key));

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

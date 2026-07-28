import { Link } from "react-router-dom";

export default function ForbiddenPage(){

return(

<div className="flex min-h-screen items-center justify-center">

<div className="text-center">

<h1 className="text-6xl font-bold">

403

</h1>

<p className="mt-4">

Permission Denied

</p>

<Link

to="/"

className="mt-6 inline-block rounded bg-blue-600 px-5 py-2 text-white"

>

Dashboard

</Link>

</div>

</div>

);

}

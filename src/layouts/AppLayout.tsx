import { Outlet } from "react-router-dom";

import Sidebar from "@/components/navigation/Sidebar";
import Header from "@/components/navigation/Header";

export default function AppLayout(){

return(

<div className="flex">

<Sidebar/>

<div className="flex-1">

<Header/>

<main className="p-6">

<Outlet/>

</main>

</div>

</div>

);

}

import { NavLink } from "react-router-dom";

const menus=[

["Dashboard","/"],

["Purchase Requisition","/purchase-requisitions"],

["Purchase Orders","/purchase-orders"],


["Inventory","/inventory"],

["Products","/products"],

["Suppliers","/suppliers"],

["COA","/chart-of-accounts"],

["Users","/users"],

["Settings","/settings"],

];

export default function Sidebar(){

return(

<div className="h-screen w-64 border-r bg-white">

<div className="border-b p-6 text-2xl font-bold">

ERP

</div>

<nav className="flex flex-col p-3">

{

menus.map(([title,url])=>(

<NavLink

key={url}

to={url}

className="rounded-lg px-4 py-3 hover:bg-slate-100"

>

{title}

</NavLink>

))

}

</nav>

</div>

);

}

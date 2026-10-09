export const menu=[

{
title:"Dashboard",
url:"/",
},

{
title:"Purchasing",
children:[
{
title:"Purchase Requisition",
url:"/purchase-requisitions",
},
{
title:"Purchase Order",
url:"/purchase-orders",
},
],
},

{
title:"Warehouse",
children:[

{
title:"Put Away",
url:"/put-away",
},
{
title:"Inventory",
url:"/inventory",
},
{
title:"Stock Card",
url:"/stock-card",
},
],
},

{
title:"Master Data",
children:[
{
title:"Catering Items",
url:"/products",
},
{ title:"Hotel Items", url:"/hotel-items" },
{
title:"Suppliers",
url:"/suppliers",
},
{
title:"Warehouses",
url:"/warehouses",
},
{
title:"Chart Of Accounts",
url:"/chart-of-accounts",
},
],
},

{
title:"Administration",
children:[
{
title:"Users",
url:"/users",
},
{
title:"Roles",
url:"/roles",
},
{
title:"Settings",
url:"/settings",
},
],
},

];

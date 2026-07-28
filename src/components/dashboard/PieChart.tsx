import{

PieChart,
Pie,
Cell,
Tooltip,
ResponsiveContainer,

}from"recharts";

export default function DashboardPie({

data,

}:any){

return(

<div className="h-80">

<ResponsiveContainer>

<PieChart>

<Pie

data={data}

dataKey="value"

nameKey="name"

outerRadius={110}

>

{

data.map((_:any,index:number)=>(

<Cell key={index}/>

))

}

</Pie>

<Tooltip/>

</PieChart>

</ResponsiveContainer>

</div>

);

}

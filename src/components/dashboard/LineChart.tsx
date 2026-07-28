import{

LineChart,
Line,
CartesianGrid,
XAxis,
YAxis,
Tooltip,
ResponsiveContainer,

}from"recharts";

export default function DashboardLineChart({

data,

}:any){

return(

<div className="h-80">

<ResponsiveContainer>

<LineChart data={data}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="month"/>

<YAxis/>

<Tooltip/>

<Line

type="monotone"

dataKey="value"

/>

</LineChart>

</ResponsiveContainer>

</div>

);

}

import{

Table,
THead,
TBody,
TR,
TH,
TD,

}from"@/components/ui/Table";

interface Column{

key:string;

title:string;

render?:(row:any)=>React.ReactNode;

}

interface Props{

columns:Column[];

rows:any[];

}

export default function DataTable({

columns,

rows,

}:Props){

return(

<Table>

<THead>

<TR>

{

columns.map(col=>(

<TH key={col.key}>

{col.title}

</TH>

))

}

</TR>

</THead>

<TBody>

{

rows.map((row,index)=>(

<TR key={index}>

{

columns.map(col=>(

<TD key={col.key}>

{

col.render

?

col.render(row)

:

row[col.key]

}

</TD>

))

}

</TR>

))

}

</TBody>

</Table>

);

}

import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

export function exportPdf(

title:string,

rows:any[],

){

const pdf=new jsPDF();

pdf.text(title,14,16);

autoTable(pdf,{

head:[Object.keys(rows[0]||{})],

body:rows.map(

Object.values,

),

startY:24,

});

pdf.save(

`${title}.pdf`,

);

}

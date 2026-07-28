import * as XLSX from "xlsx";

export function exportExcel(

rows:any[],

fileName:string,

){

const worksheet=

XLSX.utils.json_to_sheet(rows);

const workbook=

XLSX.utils.book_new();

XLSX.utils.book_append_sheet(

workbook,

worksheet,

"Sheet1",

);

XLSX.writeFile(

workbook,

`${fileName}.xlsx`,

);

}

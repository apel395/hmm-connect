import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

/** Export the loaded purchasing document, with all item rows and signature text. */
export async function downloadDocumentPdf(article: HTMLElement, name: string) {
  const pdf = new jsPDF({ unit: "mm", format: "a4" });
  let y = 12;
  const image = async (element: HTMLImageElement, x: number, top: number, width: number, height: number) => {
    if(!element.complete)await element.decode();
    const canvas=document.createElement("canvas");
    canvas.width=element.naturalWidth||240;canvas.height=element.naturalHeight||100;
    const context=canvas.getContext("2d");
    if(!context)throw new Error("Image export unavailable");
    context.drawImage(element,0,0,canvas.width,canvas.height);
    pdf.addImage(canvas.toDataURL("image/png"),"PNG",x,top,width,height);
  };
  const logo=article.querySelector<HTMLImageElement>("header img");
  if(logo){await image(logo,13,y,30,Math.min(20,30*(logo.naturalHeight||100)/(logo.naturalWidth||240)));y+=23;}

  const text = (value: string, size = 9) => {
    pdf.setFontSize(size);
    const lines = pdf.splitTextToSize(value, 184) as string[];
    for (const line of lines) {
      if (y > 278) { pdf.addPage(); y = 12; }
      pdf.text(line, 13, y); y += size * .42 + 1;
    }
    y += 2;
  };
  const header = article.querySelector("header");
  if (header) text((header as HTMLElement).innerText, 9);
  text(article.querySelector("h1")?.textContent || "Purchasing document", 13);
  const stamp = article.querySelector("[data-print-stamp]");
  if (stamp?.textContent) text(stamp.textContent, 8);
  const fields = article.querySelector("[data-print-fields]");
  if (fields) text((fields as HTMLElement).innerText, 8);
  const table = article.querySelector("table");
  if (table) {
    const columnStyles: Record<number,{halign:"left"|"right"|"center";fontStyle?:"bold"}>={};
    table.querySelectorAll("thead th").forEach((cell,index)=>{columnStyles[index]={halign:cell.classList.contains("text-right")?"right":cell.classList.contains("text-center")?"center":"left",...(index===0?{fontStyle:"bold" as const}:{})};});
    autoTable(pdf, { html: table, columnStyles, startY: y, margin: { left: 13, right: 13, top: 12, bottom: 14 },
      styles: { fontSize: 8, cellPadding: 1.5, overflow: "linebreak" }, headStyles: { fillColor: [22, 77, 65] },
      showHead: "everyPage" });
    y = (pdf as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 6;
  }
  article.querySelectorAll("[data-print-after-table]").forEach(element => text((element as HTMLElement).innerText, 8));
  const signatures = article.querySelector("[data-print-signatures]");
  if (signatures) {
    y+=8;
    const boxes=Array.from(signatures.children);
    for(let offset=0;offset<boxes.length;offset+=4){
      if(y+42>278){pdf.addPage();y=12;}
      for(const [index,box] of boxes.slice(offset,offset+4).entries()){
        const x=13+index*46;
        pdf.setFontSize(7);
        pdf.text((box.children[0]?.textContent||"").trim(),x,y);
        const signature=box.querySelector("img");
        if(signature)await image(signature,x,y+3,32,10);
        pdf.line(x,y+16,x+40,y+16);
        const details=Array.from(box.children).slice(2).map(node=>node.textContent||"").join("\n");
        pdf.text(pdf.splitTextToSize(details,42),x,y+20);
      }
      y+=43;
    }
  }
  const pages=pdf.getNumberOfPages();
  for(let page=1;page<=pages;page++){pdf.setPage(page);pdf.setFontSize(7);pdf.text(`${name} · ${page} / ${pages}`,13,290);}
  pdf.save(`${name.replace(/[^a-zA-Z0-9_-]/g, "-")}.pdf`);
}

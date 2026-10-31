import { useEffect, useState, useRef, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { attachNativePrintTracking, createPrintSession, stampText, type PrintTarget, type PrintStamp, type PrintWindow } from "./printTracking";
import Button from "@/components/ui/Button";
import { Printer } from "lucide-react";
import { toast } from "sonner";

export interface PrintField {
  label: string;
  value?: ReactNode;
}

export interface PrintColumn<Row> {
  label: string;
  align?: "left" | "center" | "right";
  render: (row: Row, index: number) => ReactNode;
}

export interface PrintTotal {
  label: string;
  value: ReactNode;
  emphasis?: boolean;
}

export interface PrintSignature {
  label: string;
  name?: ReactNode;
  imageSrc?: string;
  signedAt?: string | null;
  status?: ReactNode;
}

interface Props<Row> {
  title: string;
  printTarget?: PrintTarget;
  showLogo?: boolean;
  documentNumber?: ReactNode;
  documentDate?: ReactNode;
  status?: ReactNode;
  fields?: PrintField[];
  columns: PrintColumn<Row>[];
  rows: Row[];
  rowKey?: (row: Row, index: number) => string | number;
  totals?: PrintTotal[];
  notes?: ReactNode;
  extraAfterTable?: ReactNode;
  signatures?: PrintSignature[];
  authenticity?: PrintField[];
  footer?: ReactNode;
}

const alignClass = { left: "text-left", center: "text-center", right: "text-right" } as const;

const timestamp = (value?: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("id-ID", { timeZone:"Asia/Jakarta", day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit", hour12:false }) + " WIB";
};

export default function DocumentPrintTemplate<Row>({
  title,
  printTarget,
  showLogo = true,
  documentNumber,
  documentDate,
  status,
  fields = [],
  columns,
  rows,
  rowKey,
  totals = [],
  notes,
  extraAfterTable,
  signatures,
  authenticity = [],
  footer,
}: Props<Row>) {
  const [printing,setPrinting]=useState(false);
  const printingRef=useRef(false);
  const articleRef=useRef<HTMLElement>(null);
  const [tracking,setTracking]=useState<PrintStamp|null>(null);
  const trackingKind=printTarget?.kind;
  const trackingId=printTarget?.id;
  const trackingRevision=printTarget?.revision;
  useEffect(()=>{
    const match=window.location.pathname?.match(/\/(purchase-requisitions|market-lists|purchase-orders|receiving|goods-receipts|store-requests|stock-opnames)\/(\d+)\/print/);
    const kinds:Record<string,string>={"purchase-requisitions":"PURCHASE_REQUISITION","market-lists":"MARKET_LIST","purchase-orders":"PURCHASE_ORDER","receiving":"GOODS_RECEIPT","goods-receipts":"GOODS_RECEIPT","store-requests":"STORE_REQUEST","stock-opnames":"STOCK_OPNAME"};
    const context=trackingKind&&trackingId!=null?{kind:trackingKind,id:trackingId,revision:trackingRevision}:(match?{kind:kinds[match[1]],id:Number(match[2])}:undefined);
    if(!context)return;
    const session=createPrintSession(context);
    const target=window as PrintWindow;
    const issue=async()=>{const stamp=await session.issue("PRINT_DIALOG");flushSync(()=>setTracking(stamp));};
    const native=attachNativePrintTracking(window,issue,()=>toast.error("Print attempt could not be recorded. Refresh and try again."));
    const prepare=async()=>{await issue();native.prepared();};
    const pdf=async()=>{
      if(printingRef.current||!articleRef.current)return;
      printingRef.current=true;setPrinting(true);
      try {
        const {downloadDocumentPdf}=await import("./documentPdf");
        const stamp=await session.issue("PDF_DOWNLOAD");flushSync(()=>setTracking(stamp));
        if(!articleRef.current)throw new Error("Preview closed");
        await downloadDocumentPdf(articleRef.current,String(documentNumber??"document"));
      } finally {printingRef.current=false;setPrinting(false);}
    };
    target.mmhPreparePrint=prepare;
    if(trackingKind)target.mmhDownloadPdf=pdf;
    return()=>{native.dispose();if(target.mmhPreparePrint===prepare)delete target.mmhPreparePrint;if(target.mmhDownloadPdf===pdf)delete target.mmhDownloadPdf;};
  },[documentNumber,trackingKind,trackingId,trackingRevision]);
  const printCopy=async()=>{
    if(printingRef.current)return;
    printingRef.current=true;setPrinting(true);
    try {await (window as PrintWindow).mmhPreparePrint?.();window.print();}
    catch {toast.error("Unable to record print attempt. Refresh the preview if the document changed.");}
    finally {printingRef.current=false;setPrinting(false);}
  };
  const downloadPdf=async()=>{
    try {await (window as PrintWindow).mmhDownloadPdf?.();}
    catch {toast.error("Unable to prepare PDF. Refresh the preview if the document changed.");}
  };
  const visibleAuthenticity = authenticity.filter((field) => field.value !== undefined && field.value !== null && field.value !== "");
  return <article ref={articleRef} data-print-ready="true" className="print-document mx-auto min-h-[277mm] max-w-[210mm] bg-white px-8 py-7 text-[12px] text-black">
    <style>{`@page{size:A4 portrait;margin:10mm}@media print{body{background:#fff!important}.print-document{max-width:none!important;min-height:auto!important;padding:0!important}.print-document thead{display:table-header-group}.print-document tr{break-inside:avoid;page-break-inside:avoid}.avoid-break{break-inside:avoid;page-break-inside:avoid}}`}</style>
    <div className="mb-2 flex justify-end gap-2 print:hidden">{printTarget&&<Button variant="outline" disabled={printing} onClick={downloadPdf}>Download PDF</Button>}<Button variant="outline" disabled={printing} aria-label="Print document" onClick={printCopy}><Printer size={16}/></Button></div>
    {tracking && <div data-print-stamp className="mb-2 text-right text-xs font-semibold">{stampText(tracking)}</div>}
    <header className="grid grid-cols-[1.35fr_1fr] items-center gap-8 border-b border-black pb-4">
      <div className="flex items-center gap-4">
        {showLogo && <img src="/logoprint.jpeg" alt="PT. Mutiara Merdeka Hotel" className="h-16 w-auto shrink-0 object-contain" />}
        <div className="leading-5">
          <div className="text-[17px] font-bold tracking-wide">PT. MUTIARA MERDEKA HOTEL</div>
          <div>Jalan Yos Sudarso No 12 A PO Box 1129</div>
          <div>Pekanbaru - Riau</div>
          <div>Telp. 0761-31272</div>
        </div>
      </div>
      <dl className="grid grid-cols-[auto_1fr] content-start gap-x-3 gap-y-1">
        <dt className="font-semibold">DATE:</dt><dd>{documentDate ?? "—"}</dd>
        <dt className="font-semibold">DOCUMENT #:</dt><dd className="font-mono">{documentNumber ?? "—"}</dd>
        {status != null && <><dt className="font-semibold">STATUS:</dt><dd>{status}</dd></>}
      </dl>
    </header>

    {!!fields.length && <section data-print-fields className="mt-3 grid grid-cols-2 gap-x-10 gap-y-1.5">
      {fields.filter((field) => field.value !== undefined && field.value !== null && field.value !== "").map((field, index) => <div key={`${field.label}-${index}`} className="grid grid-cols-[120px_1fr] gap-2"><span className="font-semibold">{field.label}:</span><span>{field.value}</span></div>)}
    </section>}

    <h1 className="my-4 text-center text-[18px] font-bold tracking-[0.16em]">{title.toUpperCase()}</h1>

    <table className="w-full border-collapse">
      <thead><tr>{columns.map((column, index) => <th key={`${column.label}-${index}`} className={`border-y border-black px-2 py-2 font-bold ${alignClass[column.align ?? "left"]}`}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, rowIndex) => <tr key={rowKey ? rowKey(row, rowIndex) : rowIndex}>{columns.map((column, columnIndex) => <td key={columnIndex} className={`border-b border-slate-300 px-2 py-1 align-top ${alignClass[column.align ?? "left"]}`}>{column.render(row, rowIndex)}</td>)}</tr>)}</tbody>
    </table>

    {!!totals.length && <div data-print-after-table className="ml-auto mt-3 w-[48%]">
      {totals.map((total, index) => <div key={`${total.label}-${index}`} className={`grid grid-cols-[1fr_auto] gap-5 border-b px-2 py-1.5 ${total.emphasis ? "border-black text-[14px] font-bold" : "border-slate-300"}`}><span className="text-right">{total.label}</span><span className="min-w-28 text-right tabular-nums">{total.value}</span></div>)}
    </div>}

    <div data-print-after-table>{extraAfterTable}</div>

    <section data-print-after-table className="avoid-break mt-4"><div className="font-semibold">NOTES:</div><div className="mt-1 min-h-6 border-b border-black py-2">{notes || "—"}</div></section>

    {!!signatures?.length && <section data-print-signatures className={`avoid-break mt-4 grid gap-4 text-center ${signatures.length >= 4 ? "grid-cols-4" : signatures.length === 3 ? "grid-cols-3" : signatures.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}>
      {signatures.map((signature, index) => (
        <div key={`${signature.label}-${index}`}>
          <div className="text-[10px] font-semibold">{signature.label}</div>
          <div className="flex h-10 items-end justify-center pb-1" aria-label="Signature space">
            {signature.imageSrc && <img src={signature.imageSrc} alt="" className="max-h-9 max-w-full object-contain" />}
          </div>
          <div className="border-t border-black pt-1 text-[11px] font-semibold">{signature.name ?? "—"}</div>
          {signature.status != null && <div className="mt-0.5 text-[10px] uppercase text-slate-600">{signature.status}</div>}
          {signature.signedAt && <div className="mt-0.5 text-[10px] text-slate-600">{timestamp(signature.signedAt)}</div>}
        </div>
      ))}
    </section>}

    {!!visibleAuthenticity.length && <section className="avoid-break mt-8 border border-slate-400 p-3 text-[10px]">
      <div className="mb-2 font-bold tracking-wide">DOCUMENT AUTHENTICITY</div>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1">
        {visibleAuthenticity.map((field, index) => (
          <div key={`${field.label}-${index}`} className="grid grid-cols-[105px_1fr] gap-2">
            <span className="font-semibold">{field.label}</span>
            <span>{field.value}</span>
          </div>
        ))}
      </div>
    </section>}

    {footer && <footer className="mt-5 border-t pt-2 text-[10px] text-slate-600">{footer}</footer>}
  </article>;
}

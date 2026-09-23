import type { ReactNode } from "react";

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
  return parsed.toLocaleString("id-ID", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false });
};

export default function DocumentPrintTemplate<Row>({
  title,
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
  const visibleAuthenticity = authenticity.filter((field) => field.value !== undefined && field.value !== null && field.value !== "");
  return <article className="print-document mx-auto min-h-[277mm] max-w-[210mm] bg-white px-8 py-7 text-[12px] text-black">
    <style>{`@page{size:A4 portrait;margin:10mm}@media print{body{background:#fff!important}.print-document{max-width:none!important;min-height:auto!important;padding:0!important}.print-document thead{display:table-header-group}.print-document tr{break-inside:avoid;page-break-inside:avoid}.avoid-break{break-inside:avoid;page-break-inside:avoid}}`}</style>
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

    {!!fields.length && <section className="mt-3 grid grid-cols-2 gap-x-10 gap-y-1.5">
      {fields.filter((field) => field.value !== undefined && field.value !== null && field.value !== "").map((field, index) => <div key={`${field.label}-${index}`} className="grid grid-cols-[120px_1fr] gap-2"><span className="font-semibold">{field.label}:</span><span>{field.value}</span></div>)}
    </section>}

    <h1 className="my-6 text-center text-[18px] font-bold tracking-[0.16em]">{title.toUpperCase()}</h1>

    <table className="w-full border-collapse">
      <thead><tr>{columns.map((column, index) => <th key={`${column.label}-${index}`} className={`border-y border-black px-2 py-2 font-bold ${alignClass[column.align ?? "left"]}`}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, rowIndex) => <tr key={rowKey ? rowKey(row, rowIndex) : rowIndex}>{columns.map((column, columnIndex) => <td key={columnIndex} className={`border-b border-slate-300 px-2 py-2 align-top ${alignClass[column.align ?? "left"]}`}>{column.render(row, rowIndex)}</td>)}</tr>)}</tbody>
    </table>

    {!!totals.length && <div className="ml-auto mt-3 w-[48%]">
      {totals.map((total, index) => <div key={`${total.label}-${index}`} className={`grid grid-cols-[1fr_auto] gap-5 border-b px-2 py-1.5 ${total.emphasis ? "border-black text-[14px] font-bold" : "border-slate-300"}`}><span className="text-right">{total.label}</span><span className="min-w-28 text-right tabular-nums">{total.value}</span></div>)}
    </div>}

    {extraAfterTable}

    <section className="avoid-break mt-7"><div className="font-semibold">NOTES:</div><div className="mt-1 min-h-14 border-b border-black py-2">{notes || "—"}</div></section>

    {!!signatures?.length && <section className={`avoid-break mt-12 grid gap-10 text-center ${signatures.length >= 3 ? "grid-cols-3" : signatures.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}>
      {signatures.map((signature, index) => <div key={`${signature.label}-${index}`}><div className="flex h-14 items-end justify-center">{signature.imageSrc && <img src={signature.imageSrc} alt="" className="max-h-14 max-w-full object-contain" />}</div><div className="border-t border-black pt-2 font-semibold">{signature.label}</div><div className="mt-1 text-[11px]">{signature.name ?? ""}</div></div>)}
    </section>}

    {footer && <footer className="mt-8 border-t pt-2 text-[10px] text-slate-600">{footer}</footer>}
  </article>;
}

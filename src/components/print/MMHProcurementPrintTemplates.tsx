import type { ReactNode } from "react";

export interface MMHPrintItem {
  id: number;
  product_code?: string;
  product_name: string;
  description?: string | null;
  brand?: string | null;
  spec?: string | null;
  size?: string | null;
  uom?: string;
  quantity: number;
  unit_price?: number;
  estimated_price?: number;
  total_price?: number;
  line_total?: number;
  tax_amount?: number;
  unit_cost?: number;
}

export interface MMHPrintSignature {
  label: string;
  name?: ReactNode;
  imageSrc?: string;
}

export interface MMHProcurementPrintData {
  documentNumber?: string;
  documentDate?: string;
  requesterName?: string;
  supplierName?: string;
  locationName?: string;
  businessUnitName?: string;
  departmentName?: string;
  deliveryDate?: string;
  attn?: string;
  contact?: string;
  purpose?: string;
  eventOperation?: string;
  revision?: string;
  notes?: string | null;
  subtotal: number;
  discountAmount?: number;
  taxAmount?: number;
  totalAmount: number;
  items: MMHPrintItem[];
  signatures: MMHPrintSignature[];
}

const money = (value: number) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const valueOrDash = (value?: ReactNode | null) => value || "—";
const alignClass = { left: "text-left", center: "text-center", right: "text-right" } as const;
type Align = keyof typeof alignClass;

function MMHHeader({ documentType, documentNumber, documentDate, revision, supplierName }: { documentType: "PURCHASE REQUISITION" | "PURCHASE ORDER"; documentNumber?: string; documentDate?: string; revision?: string; supplierName?: string }) {
  return <>
    <header className="grid grid-cols-[1.15fr_0.85fr] items-start border border-black">
      <div className="flex min-h-[28mm] items-start gap-3 border-r border-black p-3">
        <img src="/mutiara-merdeka-logo.svg" alt="MMH" className="mt-0.5 h-[18mm] w-[24mm] object-contain" />
        <div className="text-[10px] leading-[1.35]"><div className="text-[14px] font-bold">PT. MUTIARA MERDEKA HOTEL</div><div>Jl. Yos Sudarso 12A PO Box 1129</div><div>Pekanbaru 28154</div><div>Telp. 0761-31272 (Hunting Lines)</div></div>
      </div>
      <div className="grid min-h-[28mm] grid-cols-[auto_1fr] content-start gap-x-2 gap-y-1 p-3 text-[10px]">
        <span className="font-semibold">NO. DOK</span><span>{valueOrDash(documentNumber)}</span>
        <span className="font-semibold">NO. REV.</span><span>{valueOrDash(revision)}</span>
        {supplierName && <><span className="font-semibold">SUPPLIER</span><span>{supplierName}</span></>}
        <span className="font-semibold">DATE</span><span>{valueOrDash(documentDate)}</span>
      </div>
    </header>
    <div className="border-x border-b border-black px-3 py-2 text-center"><h1 className="text-[17px] font-bold tracking-[0.12em]">{documentType}</h1>{documentType === "PURCHASE ORDER" && <div className="mt-0.5 text-[10px] font-bold tracking-[0.18em]">REGULER</div>}</div>
  </>;
}

function MetaRow({ label, value }: { label: string; value?: ReactNode | null }) {
  return <div className="grid grid-cols-[32mm_1fr] border-b border-black last:border-b-0"><div className="border-r border-black px-2 py-1 font-semibold">{label}</div><div className="px-2 py-1">{valueOrDash(value)}</div></div>;
}

function SignatureBlock({ signature }: { signature: MMHPrintSignature }) {
  return <div className="flex min-h-[30mm] flex-col justify-end text-center"><div className="flex h-[18mm] items-end justify-center">{signature.imageSrc && <img src={signature.imageSrc} alt="" className="max-h-[16mm] max-w-[35mm] object-contain" />}</div><div className="border-t border-black pt-1 text-[9px] font-bold uppercase">{signature.label}</div><div className="mt-0.5 min-h-[12px] text-[9px]">{signature.name ?? ""}</div></div>;
}

function PrintShell({ children }: { children: ReactNode }) { return <article className="mmh-print-document mx-auto w-[190mm] max-w-none bg-white text-black">{children}</article>; }
function HeaderCell({ label, align = "left" }: { label: string; align?: Align }) { return <th className={`border border-black px-1.5 py-1.5 ${alignClass[align]}`}>{label}</th>; }

export function MMHPurchaseRequisitionPrint({ data }: { data: MMHProcurementPrintData }) {
  const tax = Number(data.taxAmount ?? 0);
  const grandTotal = Number(data.totalAmount ?? data.subtotal);
  return <PrintShell>
    <MMHHeader documentType="PURCHASE REQUISITION" documentNumber={data.documentNumber} documentDate={data.documentDate} />
    <section className="mt-3 border border-black text-[9px]"><MetaRow label="ATTN" value={data.attn ?? data.supplierName} /><MetaRow label="TELP." value={data.contact} /><MetaRow label="REQUEST DATE" value={data.documentDate} /><MetaRow label="DELIVERY DATE" value={data.deliveryDate} /><MetaRow label="LOKASI" value={data.locationName} /></section>
    <table className="mt-3 w-full table-fixed border-collapse text-[8.5px]"><colgroup>{["5%", "27%", "13%", "10%", "8%", "8%", "14%", "15%"].map((width, index) => <col key={index} style={{ width }} />)}</colgroup><thead><tr className="font-bold"><HeaderCell label="NO" align="center" /><HeaderCell label="ITEM NAME" /><HeaderCell label="BRAND" /><HeaderCell label="SIZE" align="center" /><HeaderCell label="UNIT" align="center" /><HeaderCell label="QTY" align="right" /><HeaderCell label="PRICE" align="right" /><HeaderCell label="AMOUNT" align="right" /></tr></thead><tbody>
      {data.items.map((item, index) => <tr key={item.id} className="align-top"><td className="border border-black px-1.5 py-1.5 text-center">{index + 1}</td><td className="border border-black px-1.5 py-1.5">{item.product_name}</td><td className="border border-black px-1.5 py-1.5">{valueOrDash(item.brand)}</td><td className="border border-black px-1.5 py-1.5 text-center">{valueOrDash(item.size ?? item.spec)}</td><td className="border border-black px-1.5 py-1.5 text-center">{valueOrDash(item.uom)}</td><td className="border border-black px-1.5 py-1.5 text-right tabular-nums">{item.quantity}</td><td className="border border-black px-1.5 py-1.5 text-right tabular-nums">{money(item.estimated_price ?? item.unit_price ?? 0)}</td><td className="border border-black px-1.5 py-1.5 text-right tabular-nums">{money(item.total_price ?? item.line_total ?? Number(item.quantity) * Number(item.estimated_price ?? item.unit_price ?? 0))}</td></tr>)}
      {data.items.length < 5 && Array.from({ length: 5 - data.items.length }).map((_, index) => <tr key={`blank-${index}`} className="h-[8mm]">{Array.from({ length: 8 }).map((__, cell) => <td key={cell} className="border border-black px-1.5 py-1.5">&nbsp;</td>)}</tr>)}
    </tbody></table>
    <div className="ml-auto w-[46%] text-[9px]"><div className="grid grid-cols-[1fr_32mm] border-x border-b border-black"><div className="px-2 py-1 text-right font-semibold">Total</div><div className="border-l border-black px-2 py-1 text-right tabular-nums">{money(data.subtotal)}</div></div><div className="grid grid-cols-[1fr_32mm] border-x border-b border-black"><div className="px-2 py-1 text-right font-semibold">VAT</div><div className="border-l border-black px-2 py-1 text-right tabular-nums">{money(tax)}</div></div><div className="grid grid-cols-[1fr_32mm] border-x border-b border-black font-bold"><div className="px-2 py-1 text-right">G. Total</div><div className="border-l border-black px-2 py-1 text-right tabular-nums">{money(grandTotal)}</div></div></div>
    <section className="mt-5 grid grid-cols-4 border border-black text-[9px]">{data.signatures.slice(0, 4).map((signature, index) => <div key={`${signature.label}-${index}`} className={`${index > 0 ? "border-l border-black" : ""} px-2 py-2`}><SignatureBlock signature={signature} /></div>)}</section>
    {data.notes && <div className="mt-3 border-b border-black pb-2 text-[9px]"><span className="font-semibold">CATATAN: </span>{data.notes}</div>}
  </PrintShell>;
}

export function MMHPurchaseOrderPrint({ data }: { data: MMHProcurementPrintData }) {
  return <PrintShell>
    <MMHHeader documentType="PURCHASE ORDER" documentNumber={data.documentNumber} documentDate={data.documentDate} revision={data.revision} supplierName={data.supplierName} />
    <section className="mt-3 border border-black text-[9px]"><MetaRow label="PURPOSE" value={data.purpose} /><MetaRow label="OUTLET / EVENT" value={data.eventOperation} /><MetaRow label="PO DATE" value={data.documentDate} /><MetaRow label="SUPPLIER" value={data.supplierName} /></section>
    <table className="mt-3 w-full table-fixed border-collapse text-[8.5px]"><colgroup>{["5%", "29%", "12%", "12%", "8%", "14%", "10%", "10%"].map((width, index) => <col key={index} style={{ width }} />)}</colgroup><thead><tr className="font-bold"><HeaderCell label="NO" align="center" /><HeaderCell label="DESCRIPTION" /><HeaderCell label="BRAND" /><HeaderCell label="SPECK" /><HeaderCell label="UNIT" align="center" /><HeaderCell label="QTY & DLVR DATE" align="center" /><HeaderCell label="UNIT PRICE" align="right" /><HeaderCell label="AMOUNT" align="right" /></tr></thead><tbody>
      {data.items.map((item, index) => <tr key={item.id} className="align-top"><td className="border border-black px-1.5 py-1.5 text-center">{index + 1}</td><td className="border border-black px-1.5 py-1.5">{item.description ?? item.product_name}</td><td className="border border-black px-1.5 py-1.5">{valueOrDash(item.brand)}</td><td className="border border-black px-1.5 py-1.5">{valueOrDash(item.spec ?? item.size)}</td><td className="border border-black px-1.5 py-1.5 text-center">{valueOrDash(item.uom)}</td><td className="border border-black px-1.5 py-1.5 text-center tabular-nums">{item.quantity}<br />{valueOrDash(data.deliveryDate)}</td><td className="border border-black px-1.5 py-1.5 text-right tabular-nums">{money(item.unit_price ?? 0)}</td><td className="border border-black px-1.5 py-1.5 text-right tabular-nums">{money(item.total_price ?? item.line_total ?? Number(item.quantity) * Number(item.unit_price ?? 0))}</td></tr>)}
      {data.items.length < 5 && Array.from({ length: 5 - data.items.length }).map((_, index) => <tr key={`blank-${index}`} className="h-[8mm]">{Array.from({ length: 8 }).map((__, cell) => <td key={cell} className="border border-black px-1.5 py-1.5">&nbsp;</td>)}</tr>)}
    </tbody></table>
    <div className="ml-auto w-[36%] border-x border-b border-black text-[9px] font-bold"><div className="grid grid-cols-[1fr_32mm]"><div className="px-2 py-1 text-right">TOTAL</div><div className="border-l border-black px-2 py-1 text-right tabular-nums">{money(data.totalAmount)}</div></div></div>
    <section className="mt-8 grid grid-cols-3 gap-6 text-[9px]">{data.signatures.slice(0, 3).map((signature, index) => <SignatureBlock key={`${signature.label}-${index}`} signature={signature} />)}</section>
    {data.notes && <div className="mt-4 border-b border-black pb-2 text-[9px]"><span className="font-semibold">CATATAN: </span>{data.notes}</div>}
  </PrintShell>;
}

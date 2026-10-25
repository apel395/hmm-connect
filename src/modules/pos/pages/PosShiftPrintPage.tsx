import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Button from "@/components/ui/Button";
import useAuthStore from "@/store/auth";
import { operationsApi } from "../operationsApi";
const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{style:"currency",currency:"IDR"});
export default function PosShiftPrintPage(){
  const {id}=useParams();const owner=useAuthStore(s=>s.user?.id);
  const query=useQuery({queryKey:["pos-shift-report",owner,id],queryFn:async()=>(await operationsApi.shift(Number(id))).data,enabled:Boolean(id)});
  if(query.isLoading)return <p>Loading shift report…</p>;
  if(query.isError||!query.data)return <p role="alert">This shift report is unavailable or outside your access.</p>;
  const s=query.data;
  return <article className="mx-auto max-w-4xl space-y-3 bg-white p-4 text-sm">
    <div className="flex justify-end print:hidden"><Button onClick={()=>window.print()}>Print shift report</Button></div>
    <h1 className="text-xl font-bold">MMH · Cashier Shift #{s.id}</h1><p>{s.location_name} · {s.outlet_name} · {s.cashier_name} · {s.status}</p>
    <p>Opened: {s.opened_at} {s.closed_at?` · Closed: ${s.closed_at}`:" · Provisional open shift"}</p>
    <div className="grid grid-cols-2 gap-2 border-y py-3"><span>Opening cash</span><strong className="text-right">{money(s.opening_cash)}</strong><span>Cash sales</span><strong className="text-right">{money(s.payments.CASH)}</strong><span>Card sales</span><strong className="text-right">{money(s.payments.CARD)}</strong><span>Bank sales</span><strong className="text-right">{money(s.payments.BANK_TRANSFER)}</strong><span>Service charge</span><strong className="text-right">{money(s.service_charge)}</strong><span>PBJT</span><strong className="text-right">{money(s.pbjt)}</strong><span>Expected cash</span><strong className="text-right">{money(s.expected_cash)}</strong><span>Counted cash</span><strong className="text-right">{s.counted_cash===null?"—":money(s.counted_cash)}</strong><span>Difference</span><strong className="text-right">{s.cash_difference===null?"—":money(s.cash_difference)}</strong></div>
    <table className="w-full text-left"><thead><tr><th>Transaction</th><th>Method</th><th className="text-right">Amount</th></tr></thead><tbody>{s.transactions.map(t=><tr key={t.id} className="border-t"><td className="py-1">{t.number}</td><td>{t.method}</td><td className="text-right">{money(t.total)}</td></tr>)}</tbody><tfoot><tr className="border-t font-bold"><td colSpan={2}>Total sales</td><td className="text-right">{money(s.gross)}</td></tr></tfoot></table>
    {s.difference_reason&&<p>Difference reason: {s.difference_reason}</p>}
    <div className="pt-8">Cashier: {s.cashier_name}<div className="h-14"/><span className="border-t border-slate-400 px-12">Signature</span></div>
  </article>;
}

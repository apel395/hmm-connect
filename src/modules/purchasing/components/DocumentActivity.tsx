import { useState } from "react";
import Card from "@/components/ui/Card";

export interface DocumentActivityItem { id: number; action: string; summary: string; actor_name?: string | null; occurred_at: string }

export default function DocumentActivity({ events = [] }: { events?: DocumentActivityItem[] }) {
  const [printsOnly,setPrintsOnly]=useState(false);
  const isPrint=(event:DocumentActivityItem)=>["PRINT","PDF_DOWNLOAD"].includes(event.action);
  const visible=printsOnly?events.filter(isPrint):events;
  const printCount=events.filter(event=>event.action==="PRINT").length;
  const pdfCount=events.filter(event=>event.action==="PDF_DOWNLOAD").length;
  return <Card><div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-semibold">Activity History</h2><button type="button" className="text-xs text-emerald-700" aria-pressed={printsOnly} onClick={()=>setPrintsOnly(!printsOnly)}>Print attempts {printCount} · PDF downloads {pdfCount}</button></div>{visible.length === 0 ? <p className="text-sm text-slate-500">No activity recorded.</p> : <div className="divide-y">{visible.map((event) => <div key={event.id} className="grid gap-1 py-3 text-sm md:grid-cols-4"><div>{new Date(event.occurred_at).toLocaleString("id-ID",{timeZone:"Asia/Jakarta"})+" WIB"}</div><div className="font-medium">{event.action==="PRINT"?"Print attempt":event.action==="PDF_DOWNLOAD"?"PDF download request":event.action}</div><div>{event.actor_name ?? "System"}</div><div className="text-slate-600">{event.summary}</div></div>)}</div>}</Card>;
}

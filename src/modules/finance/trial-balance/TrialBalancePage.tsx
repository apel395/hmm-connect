import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { exportTrialBalanceXlsx, getTrialBalance, TrialBalanceFilters } from "./api";
import { listLocations } from "@/modules/admin/organization/api";
import SearchableSelect from "@/components/form/SearchableSelect";

const today = new Date().toISOString().slice(0, 10);
const monthStart = `${today.slice(0, 8)}01`;
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function TrialBalancePage() {
  const [draft, setDraft] = useState<TrialBalanceFilters>({ date_from: monthStart, date_to: today, page: 1, page_size: 50, search: "", include_zero_balance: false });
  const [filters, setFilters] = useState<TrialBalanceFilters>(draft);
  const [exporting, setExporting] = useState(false);
  const locations = useQuery({
    queryKey: ["trial-balance-locations"],
    queryFn: () => listLocations({ is_active: true }),
  });
  useEffect(() => {
    if (locations.data?.length === 1 && !draft.location_id) {
      const location_id = locations.data[0].id;
      setDraft((current) => ({ ...current, location_id }));
      setFilters((current) => ({ ...current, location_id, page: 1 }));
    }
  }, [locations.data, draft.location_id]);
  const query = useQuery({ queryKey: ["trial-balance", filters], queryFn: () => getTrialBalance(filters) });
  const data = query.data;
  const printParams = Object.fromEntries(Object.entries(filters).filter(([key, value]) => key !== "page" && key !== "page_size" && value !== "" && value !== undefined));
  const printQuery = new URLSearchParams(Object.fromEntries(Object.entries(printParams).map(([key, value]) => [key, String(value)]))).toString();
  const printSrc = `/journal/trial-balance/print${printQuery ? `?${printQuery}` : ""}`;

  const downloadExcel = async () => {
    setExporting(true);
    try {
      await exportTrialBalanceXlsx(filters);
    } catch {
      toast.error("Trial Balance Excel export failed.");
    } finally {
      setExporting(false);
    }
  };

  return <div className="space-y-5">
    <PageHeader title="Trial Balance" description="Starting debit and credit values, period activity, and closing debit and credit by account." actions={<>
<Button variant="outline" disabled={!data || exporting} loading={exporting} onClick={downloadExcel}>Export Excel</Button>
<PrintPreviewButton src={printSrc} title="Trial Balance" ariaLabel="Preview trial balance" label="Print" />
</>} />
    <Card><form className="grid gap-3 md:grid-cols-5" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft, page: 1 }); }}>
      <label className="text-sm">From<input className={`${input} mt-1 w-full`} type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })}/></label>
      <label className="text-sm">To<input className={`${input} mt-1 w-full`} type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}/></label>
      <label className="text-sm">Search<input className={`${input} mt-1 w-full`} placeholder="Account code or name" value={draft.search || ""} onChange={(e) => setDraft({ ...draft, search: e.target.value })}/></label>
      <label className="text-sm">Location<SearchableSelect value={draft.location_id} disabled={(locations.data?.length ?? 0) <= 1} placeholder="Type location code or name..." options={(locations.data??[]).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}))} onChange={(id)=>setDraft({...draft,location_id:id})}/></label>
      <div className="flex items-end gap-2"><Button type="submit">Apply</Button><label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={Boolean(draft.include_zero_balance)} onChange={(e) => setDraft({ ...draft, include_zero_balance: e.target.checked })}/>Include zero balance</label></div>
    </form></Card>

    <Card className="overflow-x-auto p-0">{query.isLoading?<div className="p-10 text-center text-sm text-slate-500">Loading trial balance…</div>:query.isError?<div className="p-10 text-center text-sm text-red-600">Trial balance could not be loaded.</div>:<Table variant="grid"><THead><TR><TH>COA No.</TH><TH>COA Name</TH><TH className="text-right">Opening Debit</TH><TH className="text-right">Opening Credit</TH><TH className="text-right">Debit Movement</TH><TH className="text-right">Credit Movement</TH><TH className="text-right">Closing Debit</TH><TH className="text-right">Closing Credit</TH><TH>Status</TH></TR></THead><TBody>{data?.items.map((row)=>{const glParams=new URLSearchParams({account_id:String(row.account_id),date_from:filters.date_from,date_to:filters.date_to,...(filters.location_id?{location_id:String(filters.location_id)}:{})}).toString();return <TR key={row.account_id}><TD className="font-medium"><Link className="text-emerald-700 hover:underline" to={`/general-ledger?${glParams}`}>{row.account_code}</Link></TD><TD className="font-medium"><Link className="text-emerald-700 hover:underline" to={`/general-ledger?${glParams}`}>{row.account_name}</Link></TD><TD className="text-right">{money(row.opening_debit)}</TD><TD className="text-right">{money(row.opening_credit)}</TD><TD className="text-right">{money(row.period_debit)}</TD><TD className="text-right">{money(row.period_credit)}</TD><TD className="text-right">{money(row.closing_debit)}</TD><TD className="text-right">{money(row.closing_credit)}</TD><TD><span className={row.status === "ABNORMAL" ? "font-medium text-amber-700" : "text-slate-700"}>{row.status === "ABNORMAL" ? "Abnormal" : "Normal"}</span></TD></TR>})}{data && <TR><TD colSpan={8} className="text-right font-semibold">Trial Balance</TD><TD className={data.summary.is_balanced ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>{data.summary.is_balanced ? "Balanced" : "Unbalanced"}</TD></TR>}</TBody></Table>}</Card>

    <div className="flex justify-end gap-2"><Button variant="outline" disabled={!data?.has_previous} onClick={() => setFilters({ ...filters, page: Math.max(1, Number(filters.page || 1) - 1) })}>Previous</Button><Button variant="outline" disabled={!data?.has_next} onClick={() => setFilters({ ...filters, page: Number(filters.page || 1) + 1 })}>Next</Button></div>
  </div>;
}

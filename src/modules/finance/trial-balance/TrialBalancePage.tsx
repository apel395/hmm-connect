import { useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { todayLocal } from "@/utils/dateConstraints";
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

const today = todayLocal();
const yearStart = `${today.slice(0, 4)}-01-01`;
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-8 rounded border border-slate-300 bg-white px-2 text-xs";

export default function TrialBalancePage() {
  const [draft, setDraft] = useState<TrialBalanceFilters>({ date_from: yearStart, date_to: today, page: 1, page_size: 50, search: "", include_zero_balance: false });
  const [filters, setFilters] = useState<TrialBalanceFilters>(draft);
  const [showFilters, setShowFilters] = useState(false);
  const [exporting, setExporting] = useState(false);
  const availableYears = Array.from({ length: Math.max(1, Number(today.slice(0, 4)) - 2025) }, (_, i) => 2026 + i);
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

  return <div className="space-y-2">
    <PageHeader title="Trial Balance" description={`${filters.date_from} — ${filters.date_to}`} actions={<>
<Button variant="outline" size="sm" title="Filters" aria-label="Trial Balance filters" aria-expanded={showFilters} onClick={() => setShowFilters(value => !value)}><SlidersHorizontal size={15}/></Button>
<Button variant="outline" disabled={!data || exporting} loading={exporting} onClick={downloadExcel}>Export Excel</Button>
<PrintPreviewButton src={printSrc} title="Trial Balance" ariaLabel="Preview trial balance" label="Print" />
</>} />
    {showFilters && <Card className="p-2"><form className="grid gap-2 md:grid-cols-6" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft, page: 1 }); setShowFilters(false); }}>
      <label className="text-sm">Fiscal year<select className={`${input} mt-1 w-full`} value={draft.date_from.slice(0, 4)} onChange={(e) => {
        const year = e.target.value;
        setDraft({ ...draft, date_from: `${year}-01-01`, date_to: year === today.slice(0, 4) ? today : `${year}-12-31` });
      }}>{availableYears.map(year => <option key={year} value={year}>{year}</option>)}</select></label>
      <label className="text-sm">From date<input className={`${input} mt-1 w-full`} type="date" required min={`${draft.date_from.slice(0,4)}-01-01`} max={draft.date_to} value={draft.date_from} onChange={e => setDraft({ ...draft, date_from: e.target.value })}/></label>
      <label className="text-sm">To date<input className={`${input} mt-1 w-full`} type="date" min={draft.date_from} max={`${draft.date_from.slice(0, 4)}-12-31`} value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}/></label>
      <label className="text-sm">Search<input className={`${input} mt-1 w-full`} placeholder="Account code or name" value={draft.search || ""} onChange={(e) => setDraft({ ...draft, search: e.target.value })}/></label>
      <label className="text-sm">Location<SearchableSelect value={draft.location_id} disabled={(locations.data?.length ?? 0) <= 1} placeholder="Type location code or name..." options={(locations.data??[]).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}))} onChange={(id)=>setDraft({...draft,location_id:id})}/></label>
      <div className="flex items-end gap-2"><Button type="submit">Apply</Button><label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={Boolean(draft.include_zero_balance)} onChange={(e) => setDraft({ ...draft, include_zero_balance: e.target.checked })}/>Include zero balance</label></div>
    </form></Card>}

    <Card className="overflow-x-auto p-0">{query.isLoading?<div className="p-10 text-center text-sm text-slate-500">Loading trial balance…</div>:query.isError?<div className="p-10 text-center text-sm text-red-600">Trial balance could not be loaded.</div>:<Table variant="grid" stickyHeader containerClassName="max-h-[60vh] overflow-auto print:max-h-none print:overflow-visible"><THead><TR><TH>Account</TH><TH className="text-right">Opening Balance</TH>{filters.date_from.slice(5) !== "01-01" && <><TH className="text-right">Prior Debit</TH><TH className="text-right">Prior Credit</TH></>}<TH className="text-right">Debit Movement</TH><TH className="text-right">Credit Movement</TH><TH className="text-right">Closing</TH><TH>Status</TH></TR></THead><TBody>{data?.items.map((row)=>{const glParams=new URLSearchParams({account_id:String(row.account_id),date_from:filters.date_from,date_to:filters.date_to,...(filters.location_id?{location_id:String(filters.location_id)}:{})}).toString();return <TR key={row.account_id}><TD className="font-medium"><Link className="text-emerald-700 hover:underline" to={`/general-ledger?${glParams}`}>{row.account_name}</Link></TD><TD className={`text-right ${Number(row.opening_balance) < 0 ? "text-rose-700" : ""}`}>{money(row.opening_balance)}</TD>{filters.date_from.slice(5) !== "01-01" && <><TD className="text-right">{money(row.prior_debit)}</TD><TD className="text-right">{money(row.prior_credit)}</TD></>}<TD className="text-right">{money(row.period_debit)}</TD><TD className="text-right">{money(row.period_credit)}</TD><TD className={`text-right font-medium ${Number(row.closing_balance) < 0 ? "text-rose-700" : ""}`}>{money(row.closing_balance)}</TD><TD><span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${row.status === "ABNORMAL" ? "bg-rose-50 text-rose-700 ring-rose-200" : "bg-emerald-50 text-emerald-700 ring-emerald-200"}`}>{row.status === "ABNORMAL" ? "Abnormal" : "Normal"}</span></TD></TR>})}</TBody></Table>}</Card>

    <div className="flex flex-wrap items-center justify-end gap-3">
      <label className="text-sm text-slate-600">Rows per page
        <select className={`${input} ml-2`} value={filters.page_size ?? 50} onChange={e => {
          const page_size = Number(e.target.value);
          setDraft(current => ({ ...current, page_size }));
          setFilters(current => ({ ...current, page_size, page: 1 }));
        }}>
          {[50, 100, 200].map(size => <option key={size} value={size}>{size}</option>)}
        </select>
      </label><span className="text-sm text-slate-500">{data?.total_items ?? 0} accounts</span><Button variant="outline" disabled={!data?.has_previous} onClick={() => setFilters({ ...filters, page: Math.max(1, Number(filters.page || 1) - 1) })}>Previous</Button><Button variant="outline" disabled={!data?.has_next} onClick={() => setFilters({ ...filters, page: Number(filters.page || 1) + 1 })}>Next</Button></div>
  </div>;
}

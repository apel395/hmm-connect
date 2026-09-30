import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {CheckCircle2, Save} from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { openingBalanceApi, type OpeningBalanceAccount } from "./api";

function fmt(v: number) {
  return Number(v || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function money(v: number | string) {
  return Number(v || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type RowState = Record<number, { debit: string; credit: string }>;

function message(error: unknown) {
  const detail = (error as any)?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return "Unable to complete the request.";
}

export default function OpeningBalancesPage() {
  const client = useQueryClient();
  const [year, setYear] = useState(() => String(new Date().getFullYear()));
  const [rows, setRows] = useState<RowState>({});
  const [description, setDescription] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [showPreview, setShowPreview] = useState(false);

  const fiscal_year = Number(year) || new Date().getFullYear();

  const acct = useQuery({
    queryKey: ["opening-accounts", fiscal_year],
    queryFn: async () => (await openingBalanceApi.accounts(fiscal_year)).data,
  });

  const entries = useQuery({
    queryKey: ["opening-entries", fiscal_year],
    queryFn: async () => (await openingBalanceApi.list(fiscal_year)).data,
  });

  useEffect(() => {
    const next: RowState = {};
    (acct.data?.items ?? []).forEach((a: OpeningBalanceAccount) => {
      const debit = Number(a.existing_debit || 0);
      const credit = Number(a.existing_credit || 0);
      next[a.id] = {
        debit: debit > 0 ? String(debit) : "",
        credit: credit > 0 ? String(credit) : "",
      };
    });
    setRows(next);
  }, [acct.data, year]);

  const items: OpeningBalanceAccount[] = useMemo(() => acct.data?.items ?? [], [acct.data]);
  const entryItems: any[] = useMemo(() => entries.data?.items ?? [], [entries.data]);
  const openingRecorded = entryItems.length > 0;
  const entryStatusUnknown = entries.isLoading || entries.isError;
  const inputLocked = openingRecorded || entryStatusUnknown;

  const totals = useMemo(() => {
    let debit = 0, credit = 0;
    for (const a of items) {
      const d = Number(rows[a.id]?.debit) || 0;
      const c = Number(rows[a.id]?.credit) || 0;
      debit += d;
      credit += c;
    }
    return { debit, credit, diff: debit - credit };
  }, [rows, items]);

  const recordedDebit = Number(entries.data?.total_debit ?? 0);
  const recordedCredit = Number(entries.data?.total_credit ?? 0);
  const displayTotals = openingRecorded ? { debit: recordedDebit, credit: recordedCredit, diff: recordedDebit - recordedCredit } : totals;

  const linesDirty = useMemo(
    () => items.some((a) => (Number(rows[a.id]?.debit) || 0) > 0 || (Number(rows[a.id]?.credit) || 0) > 0),
    [rows, items],
  );

  const buildLines = () =>
    items
      .map((a) => {
        const d = Number(rows[a.id]?.debit) || 0;
        const c = Number(rows[a.id]?.credit) || 0;
        return { account_id: a.id, amount: d > 0 ? d : c, balance_type: d > 0 ? "DEBIT" : "CREDIT" };
      })
      .filter((l) => l.amount > 0);

  const runPreview = useMutation({
    mutationFn: () => openingBalanceApi.preview(fiscal_year, buildLines()),
    onSuccess: (res) => { setPreview(res.data); setShowPreview(true); },
    onError: (e) => toast.error(message(e)),
  });

  const save = useMutation({
    mutationFn: () => openingBalanceApi.post(fiscal_year, buildLines(), description || undefined),
    onSuccess: () => {
      toast.success(`Opening balances recorded for ${fiscal_year}.`);
      setPreview(null);
      setShowPreview(false);
      client.invalidateQueries({ queryKey: ["opening-accounts"] });
      client.invalidateQueries({ queryKey: ["opening-entries"] });
    },
    onError: (e) => toast.error(message(e)),
  });


  return (
    <div className="space-y-6">
      <PageHeader  actions={<PrintPreviewButton src={`/finance-setup/opening-balances/print?year=${fiscal_year}`} title="Opening Balance Report" ariaLabel="Preview opening balance report" label="Print" />} title="Opening Balances" description="Enter each balance-sheet account’s starting debit or credit value once per fiscal year." />

      <ModuleSummary metrics={[
        { label: "Fiscal Year", value: fiscal_year },
        { label: "Balance-Sheet Accounts", value: acct.data?.count ?? 0 },
        { label: "Total Debit", value: fmt(displayTotals.debit) },
        { label: "Total Credit", value: fmt(displayTotals.credit) },
        { label: "Difference", value: fmt(Math.abs(displayTotals.diff)) },
        { label: "Status", value: openingRecorded ? "RECORDED" : "NOT RECORDED", note: openingRecorded ? "Opening values already recorded for this fiscal year" : "Available for one-time entry" },
      ]} />

      <Card>
        {entries.isError && <div role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">Unable to check whether opening values were recorded. Retry before entering values.</div>}
        {openingRecorded && <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><div className="font-semibold">Opening balance for {fiscal_year} has already been recorded.</div><div className="mt-1">The originally entered values are shown below. New input is locked to prevent duplicate starting balances.</div></div>}
        <div className="mb-5 flex flex-wrap gap-3 items-end">
          <label className="text-sm font-medium">Fiscal Year
            <Input type="number" min={2000} max={2100} className="w-40" value={year} onChange={(e) => setYear(e.target.value)} />
          </label>
          <label className="text-sm font-medium">Description (optional)
            <Input className="w-80" disabled={inputLocked} placeholder="e.g. Opening balances FY" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
        </div>

        {acct.isLoading ? <div className="py-12"><Loading /></div> : <>
          <Table variant="grid"><THead><TR><TH>Code</TH><TH>Name</TH><TH>Type</TH><TH>Normal</TH><TH>Debit</TH><TH>Credit</TH></TR></THead>
            <TBody>
              {items.map((a) => (
                <TR key={a.id}>
                  <TD className="font-mono font-medium">{a.account_code}</TD>
                  <TD>{a.account_name}</TD>
                  <TD><span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium">{a.account_type}</span></TD>
                  <TD className="text-xs text-slate-500">{a.normal_balance}</TD>
                  <TD><Input type="number" min={0} step="0.01" disabled={inputLocked} className="w-40 font-mono" placeholder="0.00" value={rows[a.id]?.debit ?? ""} onChange={(e) => setRows({ ...rows, [a.id]: { ...rows[a.id], debit: e.target.value, credit: "" } })} /></TD>
                  <TD><Input type="number" min={0} step="0.01" disabled={inputLocked} className="w-40 font-mono" placeholder="0.00" value={rows[a.id]?.credit ?? ""} onChange={(e) => setRows({ ...rows, [a.id]: { ...rows[a.id], credit: e.target.value, debit: "" } })} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
          {!items.length && <p className="py-8 text-center text-sm text-slate-500">No balance-sheet posting accounts found.</p>}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm">
              <span className="mr-4">Total Debit: <b className="font-mono">{money(displayTotals.debit)}</b></span>
              <span className="mr-4">Total Credit: <b className="font-mono">{money(displayTotals.credit)}</b></span>
              <span>Difference: <b className={`font-mono ${displayTotals.diff === 0 ? "text-emerald-700" : "text-amber-700"}`}>{money(Math.abs(displayTotals.diff))}</b></span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" disabled={inputLocked || !linesDirty} onClick={() => runPreview.mutate()}>Preview</Button>
              <Button loading={save.isPending} disabled={inputLocked || !linesDirty || save.isPending} onClick={() => { if (window.confirm(`Record starting balances for fiscal year ${fiscal_year}? No transaction journal will be created.`)) save.mutate(); }}><Save size={16} /> Record Opening Balances</Button>
            </div>
          </div>
        </>}
      </Card>

      {entryItems.length > 0 && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div><h3 className="text-lg font-semibold">Recorded Opening Balance — {fiscal_year}</h3><p className="text-xs text-slate-500">Original starting values retained for audit and tracing.</p></div>
          </div>
          <Table variant="grid"><THead><TR><TH>Code</TH><TH>Name</TH><TH>Debit</TH><TH>Credit</TH><TH>Recorded</TH></TR></THead>
            <TBody>{entryItems.map((e) => (
              <TR key={e.id}>
                <TD className="font-mono">{e.account_code}</TD>
                <TD>{e.account_name}</TD>
                <TD className="font-mono">{e.balance_type === "DEBIT" ? money(e.amount) : "—"}</TD>
                <TD className="font-mono">{e.balance_type === "CREDIT" ? money(e.amount) : "—"}</TD>
                <TD className="text-xs text-slate-500">{e.posted_at ? new Date(e.posted_at).toLocaleString() : "—"}</TD>
              </TR>
            ))}</TBody>
          </Table>
        </Card>
      )}

      <Dialog open={showPreview} onOpenChange={(o) => !o && setShowPreview(false)}>
        <DialogContent><DialogHeader><DialogTitle>Opening Balances Preview — {fiscal_year}</DialogTitle></DialogHeader>
        <DialogBody className="space-y-4">
          {preview && <>
            <Table variant="grid"><THead><TR><TH>Account</TH><TH>Debit</TH><TH>Credit</TH></TR></THead>
              <TBody>{(preview.lines ?? []).map((l: any, i: number) => (
                <TR key={i}>
                  <TD className="font-mono">{l.account_code}</TD>
                  <TD className="font-mono">{l.balance_type === "DEBIT" ? money(l.amount) : "—"}</TD>
                  <TD className="font-mono">{l.balance_type === "CREDIT" ? money(l.amount) : "—"}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <div className={`flex items-center gap-2 text-sm ${preview.differences_ok ? "text-emerald-700" : "text-amber-700"}`}>
              {preview.differences_ok && <CheckCircle2 size={16} />}
              <span>Total Debit <b className="font-mono">{money(preview.total_debit)}</b> · Total Credit <b className="font-mono">{money(preview.total_credit)}</b> · Difference <b className="font-mono">{money(preview.difference)}</b></span>
            </div>
            <div className="text-xs text-slate-500">Only the amounts entered above will be saved as the {fiscal_year} starting snapshot.</div>
          </>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowPreview(false)}>Close</Button>
          <Button loading={save.isPending} disabled={inputLocked || !preview || save.isPending} onClick={() => { setShowPreview(false); if (window.confirm(`Record starting balances for fiscal year ${fiscal_year}?`)) save.mutate(); }}><Save size={16} /> Confirm &amp; Record</Button>
        </DialogFooter>
        </DialogContent>
      </Dialog>


    </div>
  );
}

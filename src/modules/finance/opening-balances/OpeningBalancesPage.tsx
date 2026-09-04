import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Button from "@/components/ui/Button";
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
      const bal = Number(a.existing_balance || 0);
      next[a.id] = {
        debit: a.normal_balance === "DEBIT" && bal > 0 ? String(bal) : "",
        credit: a.normal_balance === "CREDIT" && bal > 0 ? String(bal) : "",
      };
    });
    setRows(next);
  }, [acct.data, year]);

  const items: OpeningBalanceAccount[] = useMemo(() => acct.data?.items ?? [], [acct.data]);
  const entryItems: any[] = useMemo(() => entries.data?.items ?? [], [entries.data]);

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
      toast.success(`Opening balances posted for ${fiscal_year}.`);
      setPreview(null);
      setShowPreview(false);
      client.invalidateQueries({ queryKey: ["opening-accounts"] });
      client.invalidateQueries({ queryKey: ["opening-entries"] });
    },
    onError: (e) => toast.error(message(e)),
  });

  const voidAll = useMutation({
    mutationFn: () => openingBalanceApi.void(fiscal_year),
    onSuccess: () => { toast.success(`Opening balances voided for ${fiscal_year}.`); setRows({}); client.invalidateQueries({ queryKey: ["opening-accounts"] }); client.invalidateQueries({ queryKey: ["opening-entries"] }); },
    onError: (e) => toast.error(message(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Opening Balances" description="Enter the beginning-of-year balance for each balance-sheet account. Posted once per fiscal year (annual, not monthly); the balancing side goes to the Opening Balance Equity account and flows through the general ledger." />

      <ModuleSummary metrics={[
        { label: "Fiscal Year", value: fiscal_year },
        { label: "Balance-Sheet Accounts", value: acct.data?.count ?? 0 },
        { label: "Total Debit", value: fmt(totals.debit) },
        { label: "Total Credit", value: fmt(totals.credit) },
        { label: "Difference", value: fmt(Math.abs(totals.diff)), note: totals.diff !== 0 ? "Auto-contra to equity on post" : "Balanced" },
      ]} />

      <Card>
        <div className="mb-5 flex flex-wrap gap-3 items-end">
          <label className="text-sm font-medium">Fiscal Year
            <Input type="number" min={2000} max={2100} className="w-40" value={year} onChange={(e) => setYear(e.target.value)} />
          </label>
          <label className="text-sm font-medium">Description (optional)
            <Input className="w-80" placeholder="e.g. Opening balances FY" value={description} onChange={(e) => setDescription(e.target.value)} />
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
                  <TD><Input type="number" min={0} step="0.01" className="w-40 font-mono" placeholder="0.00" value={rows[a.id]?.debit ?? ""} onChange={(e) => setRows({ ...rows, [a.id]: { ...rows[a.id], debit: e.target.value, credit: "" } })} /></TD>
                  <TD><Input type="number" min={0} step="0.01" className="w-40 font-mono" placeholder="0.00" value={rows[a.id]?.credit ?? ""} onChange={(e) => setRows({ ...rows, [a.id]: { ...rows[a.id], credit: e.target.value, debit: "" } })} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
          {!items.length && <p className="py-8 text-center text-sm text-slate-500">No balance-sheet posting accounts found.</p>}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm">
              <span className="mr-4">Total Debit: <b className="font-mono">{money(totals.debit)}</b></span>
              <span className="mr-4">Total Credit: <b className="font-mono">{money(totals.credit)}</b></span>
              <span>Difference: <b className={`font-mono ${totals.diff === 0 ? "text-emerald-700" : "text-amber-700"}`}>{money(Math.abs(totals.diff))}</b></span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" disabled={!linesDirty} onClick={() => runPreview.mutate()}>Preview</Button>
              <Button loading={save.isPending} disabled={!linesDirty || save.isPending} onClick={() => { if (window.confirm(`Post opening balances for fiscal year ${fiscal_year}? This creates a posted journal.`)) save.mutate(); }}><Save size={16} /> Save &amp; Post</Button>
            </div>
          </div>
        </>}
      </Card>

      {entryItems.length > 0 && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold">Posted Entries — {fiscal_year}</h3>
            <Button variant="outline" onClick={() => { if (window.confirm(`Void all opening balances for ${fiscal_year}? The journal will be unposted and entries removed.`)) voidAll.mutate(); }}><Trash2 size={16} /> Void</Button>
          </div>
          <Table variant="grid"><THead><TR><TH>Code</TH><TH>Name</TH><TH>Type</TH><TH>Amount</TH><TH>Posted</TH></TR></THead>
            <TBody>{entryItems.map((e) => (
              <TR key={e.id}>
                <TD className="font-mono">{e.account_code}</TD>
                <TD>{e.account_name}</TD>
                <TD><span className={`rounded px-2 py-1 text-xs font-medium ${e.balance_type === "DEBIT" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}>{e.balance_type}</span></TD>
                <TD className="font-mono">{money(e.amount)}</TD>
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
            <Table variant="grid"><THead><TR><TH>Account</TH><TH>Type</TH><TH>Amount</TH><TH></TH></TR></THead>
              <TBody>{(preview.lines ?? []).map((l: any, i: number) => (
                <TR key={i}>
                  <TD className="font-mono">{l.account_code}</TD>
                  <TD><span className={`rounded px-2 py-1 text-xs font-medium ${l.balance_type === "DEBIT" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}>{l.balance_type}</span></TD>
                  <TD className="font-mono">{money(l.amount)}</TD>
                  <TD className="text-xs text-slate-500">{l.contra ? "Auto-contra (equity)" : ""}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={16} className="text-emerald-600" />
              <span>Total Debit <b className="font-mono">{money(preview.total_debit)}</b> = Total Credit <b className="font-mono">{money(preview.total_credit)}</b>.</span>
            </div>
            <div className="text-xs text-slate-500">Contra account: <span className="font-mono">{preview.equity_account.account_code}</span> — {preview.equity_account.account_name}. Posted at {fiscal_year}-01-01.</div>
          </>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowPreview(false)}>Close</Button>
          <Button loading={save.isPending} disabled={save.isPending} onClick={() => { setShowPreview(false); if (window.confirm(`Post opening balances for fiscal year ${fiscal_year}?`)) save.mutate(); }}><Save size={16} /> Confirm &amp; Post</Button>
        </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

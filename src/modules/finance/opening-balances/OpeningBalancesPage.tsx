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
import SearchableSelect from "@/components/form/SearchableSelect";

function fmt(v: number) {
  return Number(v || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function money(v: number | string) {
  return Number(v || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type RowState = Record<number, { debit: string; credit: string }>;
type Imbalance = { journal_id: number; journal_number: string; difference: string; location_id: number | null };
type CompletionLine = { account_id?: number; amount: string; balance_type: "DEBIT" | "CREDIT" };

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
  const [completionJournal, setCompletionJournal] = useState<Imbalance | null>(null);
  const [completionLines, setCompletionLines] = useState<CompletionLine[]>([]);
  const [completionDescription, setCompletionDescription] = useState("");

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
  const imbalances: Imbalance[] = entries.data?.imbalances ?? [];
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

  const balanced = Math.round(totals.debit * 100) === Math.round(totals.credit * 100);

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

  const openCompletion = (journal: Imbalance) => {
    setCompletionJournal(journal);
    setCompletionLines([{
      balance_type: Number(journal.difference) > 0 ? "CREDIT" : "DEBIT",
      amount: String(Math.abs(Number(journal.difference))),
    }]);
    setCompletionDescription("");
  };
  const completionDifference = (completionLines.reduce(
    (sum, line) => sum + (line.balance_type === "DEBIT" ? 1 : -1) * Number(line.amount || 0), 0,
  ) + Number(completionJournal?.difference || 0));
  const completionReady = completionLines.length > 0 && completionLines.every(
    (line) => line.account_id && Number(line.amount) > 0,
  ) && Math.abs(completionDifference) < 0.005;
  const complete = useMutation({
    mutationFn: () => openingBalanceApi.complete(
      completionJournal!.journal_id,
      completionLines.map((line) => ({
        account_id: line.account_id!,
        amount: Number(line.amount),
        balance_type: line.balance_type,
      })),
      completionDescription.trim() || undefined,
    ),
    onSuccess: () => {
      toast.success("Opening journal balanced with the entered account lines.");
      setCompletionJournal(null);
      client.invalidateQueries({ queryKey: ["opening-accounts"] });
      client.invalidateQueries({ queryKey: ["opening-entries"] });
      client.invalidateQueries({ queryKey: ["trial-balance"] });
      client.invalidateQueries({ queryKey: ["journal-entry"] });
      client.invalidateQueries({ queryKey: ["general-ledger"] });
    },
    onError: (e) => toast.error(message(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader  actions={<PrintPreviewButton src={`/finance-setup/opening-balances/print?year=${fiscal_year}`} title="Opening Balance Report" ariaLabel="Preview opening balance report" label="Print" />} title="Opening Balances" description="Enter the beginning-of-year balance for each balance-sheet account. Posted once per fiscal year (annual, not monthly); enter every balancing account amount yourself. Posting requires total debit to equal total credit; no account is added automatically." />

      <ModuleSummary metrics={[
        { label: "Fiscal Year", value: fiscal_year },
        { label: "Balance-Sheet Accounts", value: acct.data?.count ?? 0 },
        { label: "Total Debit", value: fmt(totals.debit) },
        { label: "Total Credit", value: fmt(totals.credit) },
        { label: "Difference", value: fmt(Math.abs(totals.diff)), note: !balanced ? "Enter the balancing account amount before posting" : "Balanced" },
        { label: "Status", value: openingRecorded ? "RECORDED" : "NOT RECORDED", note: openingRecorded ? "Opening balance already posted for this fiscal year" : "Available for one-time entry" },
      ]} />

      <Card>
        {entries.isError && <div role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">Unable to check whether opening balances were posted. Retry before entering values.</div>}
        {!inputLocked && linesDirty && !balanced && <div role="alert" className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">Debit and credit differ. Enter the balancing amount in the correct account above before posting.</div>}
        {openingRecorded && <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><div className="font-semibold">Opening balance for {fiscal_year} has already been recorded.</div><div className="mt-1">The original posted amounts are shown below. New input is locked to prevent duplicate opening balances.</div></div>}
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
              <span className="mr-4">Total Debit: <b className="font-mono">{money(totals.debit)}</b></span>
              <span className="mr-4">Total Credit: <b className="font-mono">{money(totals.credit)}</b></span>
              <span>Difference: <b className={`font-mono ${totals.diff === 0 ? "text-emerald-700" : "text-amber-700"}`}>{money(Math.abs(totals.diff))}</b></span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" disabled={inputLocked || !linesDirty} onClick={() => runPreview.mutate()}>Preview</Button>
              <Button loading={save.isPending} disabled={inputLocked || !linesDirty || !balanced || save.isPending} onClick={() => { if (window.confirm(`Post opening balances for fiscal year ${fiscal_year}? This creates a posted journal.`)) save.mutate(); }}><Save size={16} /> Save &amp; Post</Button>
            </div>
          </div>
        </>}
      </Card>

      {imbalances.length > 0 && <Card>
        <h3 className="mb-2 text-lg font-semibold text-amber-900">Opening journals awaiting manual balance</h3>
        <p className="mb-3 text-sm text-slate-600">Select the verified account and amount for each journal. The app will accept only an exact match to its remaining debit–credit difference.</p>
        <div className="space-y-2">{imbalances.map((journal) => (
          <div key={journal.journal_id} className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 p-3">
            <span className="text-sm"><b>{journal.journal_number}</b> · Location #{journal.location_id ?? "—"} · Debit–credit difference <b>{money(journal.difference)}</b></span>
            <Button variant="outline" onClick={() => openCompletion(journal)}>Enter balancing accounts</Button>
          </div>
        ))}</div>
      </Card>}

      {entryItems.length > 0 && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div><h3 className="text-lg font-semibold">Recorded Opening Balance — {fiscal_year}</h3><p className="text-xs text-slate-500">Original posted amounts retained for audit and tracing.</p></div>
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
            <Table variant="grid"><THead><TR><TH>Account</TH><TH>Type</TH><TH>Amount</TH></TR></THead>
              <TBody>{(preview.lines ?? []).map((l: any, i: number) => (
                <TR key={i}>
                  <TD className="font-mono">{l.account_code}</TD>
                  <TD><span className={`rounded px-2 py-1 text-xs font-medium ${l.balance_type === "DEBIT" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}>{l.balance_type}</span></TD>
                  <TD className="font-mono">{money(l.amount)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <div className={`flex items-center gap-2 text-sm ${preview.differences_ok ? "text-emerald-700" : "text-amber-700"}`}>
              {preview.differences_ok && <CheckCircle2 size={16} />}
              <span>Total Debit <b className="font-mono">{money(preview.total_debit)}</b> · Total Credit <b className="font-mono">{money(preview.total_credit)}</b> · Difference <b className="font-mono">{money(preview.difference)}</b></span>
            </div>
            <div className="text-xs text-slate-500">Only the amounts entered above will be posted on {fiscal_year}-01-01.</div>
          </>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowPreview(false)}>Close</Button>
          <Button loading={save.isPending} disabled={inputLocked || !preview?.differences_ok || !balanced || save.isPending} onClick={() => { setShowPreview(false); if (window.confirm(`Post opening balances for fiscal year ${fiscal_year}?`)) save.mutate(); }}><Save size={16} /> Confirm &amp; Post</Button>
        </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(completionJournal)} onOpenChange={(open) => { if (!open && !complete.isPending) setCompletionJournal(null); }}>
        <DialogContent className="max-w-3xl">
          <DialogHeader><DialogTitle>Complete {completionJournal?.journal_number}</DialogTitle></DialogHeader>
          <DialogBody className="space-y-4">
            <p className="text-sm text-amber-900">Remaining debit–credit difference: <b>{money(completionJournal?.difference ?? 0)}</b>. Add the correct account lines below. No account is chosen automatically.</p>
            <Input placeholder="Reason and supporting reference" value={completionDescription} onChange={(e) => setCompletionDescription(e.target.value)} />
            {completionLines.map((line, index) => (
              <div key={index} className="grid items-end gap-2 md:grid-cols-[1fr_120px_160px_auto]">
                <SearchableSelect label="Account" value={line.account_id} placeholder="Search account code or name" options={items.map((account) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}` }))} onChange={(value) => setCompletionLines((current) => current.map((item, i) => i === index ? { ...item, account_id: value } : item))} />
                <label className="text-sm">Side<select className="mt-1 h-10 w-full rounded border px-2" value={line.balance_type} onChange={(e) => setCompletionLines((current) => current.map((item, i) => i === index ? { ...item, balance_type: e.target.value as CompletionLine["balance_type"] } : item))}><option value="DEBIT">Debit</option><option value="CREDIT">Credit</option></select></label>
                <label className="text-sm">Amount<Input className="mt-1" type="number" min="0.01" step="0.01" value={line.amount} onChange={(e) => setCompletionLines((current) => current.map((item, i) => i === index ? { ...item, amount: e.target.value } : item))} /></label>
                <Button type="button" size="xs" variant="danger" disabled={completionLines.length === 1} onClick={() => setCompletionLines((current) => current.filter((_, i) => i !== index))}>Remove</Button>
              </div>
            ))}
            <Button type="button" variant="outline" onClick={() => setCompletionLines((current) => [...current, { balance_type: Number(completionJournal?.difference) > 0 ? "CREDIT" : "DEBIT", amount: "" }])}>Add Account</Button>
            <p className="text-sm font-medium">Difference after entered lines: {money(completionDifference)}</p>
          </DialogBody>
          <DialogFooter><Button variant="outline" onClick={() => setCompletionJournal(null)}>Cancel</Button><Button disabled={!completionReady || complete.isPending} loading={complete.isPending} onClick={() => { if (window.confirm(`Post these manual opening lines to ${completionJournal?.journal_number}?`)) complete.mutate(); }}>Post Balancing Lines</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

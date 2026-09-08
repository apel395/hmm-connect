import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {Link2, Unlink, Printer} from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { exportCsv } from "@/utils/exportCsv";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { fiscalApi, type FiscalLinkedAccount } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const PAGE_SIZE = 25;
const selectClass = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500";
const ACCOUNT_TYPES = ["REVENUE", "EXPENSE", "ASSET", "LIABILITY", "EQUITY"];

function message(error: unknown) {
  const detail = (error as any)?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return "Unable to complete the request.";
}

export default function FiscalAccountPage() {
  const client = useQueryClient();
  const [page, setPage] = useState(1), [search, setSearch] = useState("");
  const [accountTypes, setAccountTypes] = useState<string[]>(["REVENUE", "EXPENSE"]);
  const [status, setStatus] = useState<"all" | "linked" | "unlinked">("all");

  // link state
  const [linkTarget, setLinkTarget] = useState<FiscalLinkedAccount | null>(null);
  const [fiscalId, setFiscalId] = useState("");

  const typeKey = accountTypes.join(",");
  useEffect(() => setPage(1), [search, status, typeKey]);

  const params = {
    page, page_size: PAGE_SIZE,
    search: search.trim() || undefined,
    account_types: accountTypes.length ? accountTypes.join(",") : undefined,
    status,
  };
  const coa = useQuery({ queryKey: ["fiscal-linked", params], queryFn: async () => (await fiscalApi.linkedCoa(params)).data });
  const opts = useQuery({ queryKey: ["fiscal-options"], queryFn: async () => (await fiscalApi.accounts({ page_size: 100, is_header: false, sort_by: "sort_order", sort_order: "asc" })).data });

  const refresh = () => client.invalidateQueries({ queryKey: ["fiscal-linked"] });

  const addMapping = useMutation({
    mutationFn: () => fiscalApi.createMapping({ fiscal_account_id: Number(fiscalId), commercial_account_id: linkTarget!.id }),
    onSuccess: () => { toast.success("Mapping created."); setLinkTarget(null); setFiscalId(""); refresh(); },
    onError: (e) => toast.error(message(e)),
  });
  const removeMapping = useMutation({
    mutationFn: (id: number) => fiscalApi.deleteMapping(id),
    onSuccess: () => { toast.success("Mapping removed."); refresh(); },
    onError: (e) => toast.error(message(e)),
  });

  const toggleType = (t: string) =>
    setAccountTypes((prev) => prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]);

  const coaData: any = coa.data ?? {};
  const items: FiscalLinkedAccount[] = coaData.items ?? [];
  const linkedCount = items.filter((i) => i.mapping_id != null).length;
  const unlinkedCount = items.length - linkedCount;

  return (
    <div className="space-y-6">
      <FiscalWorkspaceHeader />
      <PageHeader title="Fiscal Linked Chart of Accounts" description="Commercial (MMH-Connect) accounts with their linked Coretax L1-D Jasa fiscal account. The fiscal COA appears only through its link to the commercial COA; commercial and fiscal figures are reported separately." actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportCsv("fiscal-linked-chart-of-accounts.csv", ["Code", "Name", "Type", "Fiscal Code", "Fiscal Name", "Classification", "Status"], items.map((i) => [i.commercial_code, i.commercial_name, i.account_type, i.fiscal_code ?? "", i.fiscal_name ?? "", i.klasifikasi_fiskal ?? "", i.mapping_id != null ? "Linked" : "Unlinked"]))}>Export</Button>
          <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</div>
      } />

      <ModuleSummary metrics={[
        { label: "Commercial Accounts", value: coaData.total ?? 0 },
        { label: "Linked to Fiscal", value: linkedCount, note: "Visible page" },
        { label: "Unlinked", value: unlinkedCount, note: "Visible page" },
      ]} />

      <Card>
        <div className="mb-5 flex flex-wrap gap-3">
          <Input aria-label="Search accounts" className="max-w-sm" placeholder="Search commercial or fiscal account..." value={search} onChange={(e) => setSearch(e.target.value)} />
          <div className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1">
            {ACCOUNT_TYPES.map((t) => (
              <button key={t} type="button" onClick={() => toggleType(t)}
                className={`rounded px-2 py-1 text-xs font-medium ${accountTypes.includes(t) ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{t}</button>
            ))}
          </div>
          <select className={selectClass + " max-w-40"} value={status} onChange={(e) => setStatus(e.target.value as any)}>
            <option value="all">All statuses</option>
            <option value="linked">Linked</option>
            <option value="unlinked">Unlinked</option>
          </select>
        </div>
        {coa.isLoading ? <div className="py-12"><Loading /></div> : <>
          <Table variant="grid"><THead><TR><TH>Commercial Account</TH><TH>Type</TH><TH>Linked Fiscal Account</TH><TH>Status</TH><TH>Actions</TH></TR></THead>
          <TBody>{items.map((a) => (
            <TR key={a.id}>
              <TD><span className="font-mono font-medium">{a.commercial_code}</span> <span className="ml-1">{a.commercial_name}</span></TD>
              <TD><span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium">{a.account_type}</span></TD>
              <TD>
                {a.fiscal_account_id != null ? (
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono">{a.fiscal_code} <span className="ml-1 font-sans text-slate-700">{a.fiscal_name}</span></span>
                    {a.klasifikasi_fiskal && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700">{a.klasifikasi_fiskal}</span>}
                  </div>
                ) : <span className="text-slate-400">Unlinked</span>}
              </TD>
              <TD>{a.mapping_id != null ? <span className="rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">Linked</span> : <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-500">Unlinked</span>}</TD>
              <TD>
                <div className="flex gap-1">
                  {a.mapping_id != null
                    ? <Button size="xs" variant="outline" disabled={removeMapping.isPending} onClick={() => { if (window.confirm(`Unlink ${a.commercial_name} from its fiscal account?`)) removeMapping.mutate(a.mapping_id!); }}><Unlink size={14} /> Unlink</Button>
                    : <Button size="xs" variant="outline" onClick={() => { setLinkTarget(a); setFiscalId(""); }}><Link2 size={14} /> Link</Button>}
                </div>
              </TD>
            </TR>
          ))}</TBody></Table>
          {!items.length && <p className="py-8 text-center text-sm text-slate-500">No accounts found.</p>}
          <div className="mt-4 flex items-center justify-between text-sm"><span>{coaData.total ?? 0} accounts</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page} of {Math.max(coaData.pages ?? 1, 1)}</span><Button size="sm" variant="outline" disabled={page >= (coaData.pages ?? 1)} onClick={() => setPage(page + 1)}>Next</Button></div></div>
        </>}
      </Card>

      <Dialog open={!!linkTarget} onOpenChange={(o) => !o && setLinkTarget(null)}><DialogContent><DialogHeader><DialogTitle>Link to Fiscal Account</DialogTitle></DialogHeader><DialogBody className="grid gap-4">
        <div className="rounded-md bg-slate-50 px-3 py-2 text-sm"><span className="font-mono">{linkTarget?.commercial_code}</span> — {linkTarget?.commercial_name}</div>
        <label className="text-sm font-medium">Fiscal Account
          <select className={selectClass} value={fiscalId} onChange={(e) => setFiscalId(e.target.value)}>
            <option value="">Select fiscal account</option>
            {(opts.data?.items ?? []).map((a: any) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </select>
        </label>
      </DialogBody><DialogFooter><Button variant="outline" onClick={() => setLinkTarget(null)}>Cancel</Button><Button loading={addMapping.isPending} disabled={!fiscalId} onClick={() => addMapping.mutate()}>Create Mapping</Button></DialogFooter></DialogContent></Dialog>
    </div>
  );
}

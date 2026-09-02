import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Plus, Trash2 } from "lucide-react";
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
import { fiscalApi, type FiscalAccount, type FiscalAccountPayload, type FiscalMapping } from "../api";

const PAGE_SIZE = 25;
const selectClass = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500";

const emptyForm: FiscalAccountPayload = { code: "", name: "", category: "", parent_code: null, is_header: false, is_active: true, sort_order: 0 };

function message(error: unknown) {
  const detail = (error as any)?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return "Unable to complete the request.";
}

export default function FiscalAccountPage() {
  const client = useQueryClient();
  const [tab, setTab] = useState<"coa" | "mapping">("coa");
  const [page, setPage] = useState(1), [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState<FiscalAccount | null>(null), [viewing, setViewing] = useState<FiscalAccount | null>(null);
  const [formOpen, setFormOpen] = useState(false), [form, setForm] = useState<FiscalAccountPayload>(emptyForm);

  // mapping state
  const [mPage, setMPage] = useState(1), [mSearch, setMSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [addFiscalId, setAddFiscalId] = useState(""), [mappingSearch, setMappingSearch] = useState("");
  const [pickFiscal, setPickFiscal] = useState("");

  useEffect(() => setPage(1), [search, category, status]);
  useEffect(() => setMPage(1), [mSearch]);

  const params = { page, page_size: PAGE_SIZE, search: search.trim() || undefined,
    category: category || undefined, is_active: status === "active" ? true : status === "archived" ? false : undefined,
    sort_by: "sort_order", sort_order: "asc" as const };
  const coa = useQuery({ queryKey: ["fiscal", params], queryFn: async () => (await fiscalApi.accounts(params)).data, enabled: tab === "coa" });
  const opts = useQuery({ queryKey: ["fiscal-options"], queryFn: async () => (await fiscalApi.accounts({ page_size: 500, sort_by: "sort_order", sort_order: "asc" })).data });
  const cats = useQuery({ queryKey: ["fiscal-categories"], queryFn: async () => (await fiscalApi.categories()).data });
  const mappingsQuery = useQuery({ queryKey: ["fiscal-mappings", { mPage, mSearch }], queryFn: async () => (await fiscalApi.mappings({ page: mPage, page_size: PAGE_SIZE, search: mSearch.trim() || undefined })).data, enabled: tab === "mapping" });
  const unmappedQuery = useQuery({ queryKey: ["fiscal-unmapped", { mappingSearch }], queryFn: async () => (await fiscalApi.unmappedCommercial({ page: 1, page_size: 100, search: mappingSearch.trim() || undefined })).data, enabled: addOpen });

  const refresh = () => {
    client.invalidateQueries({ queryKey: ["fiscal"] });
    client.invalidateQueries({ queryKey: ["fiscal-options"] });
    client.invalidateQueries({ queryKey: ["fiscal-categories"] });
  };
  const refreshMaps = () => client.invalidateQueries({ queryKey: ["fiscal-mappings"] });

  const save = useMutation({
    mutationFn: () => editing ? fiscalApi.updateAccount(editing.id, form) : fiscalApi.createAccount(form),
    onSuccess: () => { toast.success(editing ? "Fiscal account updated." : "Fiscal account created."); setFormOpen(false); refresh(); },
    onError: (e) => toast.error(message(e)),
  });
  const removeAccount = useMutation({
    mutationFn: (a: FiscalAccount) => fiscalApi.deleteAccount(a.id),
    onSuccess: () => { toast.success("Fiscal account deleted."); refresh(); },
    onError: (e) => toast.error(message(e)),
  });
  const addMapping = useMutation({
    mutationFn: () => fiscalApi.createMapping({ fiscal_account_id: Number(addFiscalId), commercial_account_id: Number(pickFiscal) }),
    onSuccess: () => { toast.success("Mapping created."); setAddOpen(false); setAddFiscalId(""); setPickFiscal(""); refreshMaps(); },
    onError: (e) => toast.error(message(e)),
  });
  const removeMapping = useMutation({
    mutationFn: (id: number) => fiscalApi.deleteMapping(id),
    onSuccess: () => { toast.success("Mapping removed."); refreshMaps(); },
    onError: (e) => toast.error(message(e)),
  });

  function openForm(a?: FiscalAccount) {
    setEditing(a ?? null);
    setForm(a ? { code: a.code, name: a.name, category: a.category, parent_code: a.parent_code, is_header: a.is_header, is_active: a.is_active, sort_order: a.sort_order } : { ...emptyForm });
    setFormOpen(true);
  }

  const confirmDelete = (a: FiscalAccount) => {
    if (window.confirm(`Delete fiscal account ${a.code} - ${a.name}?`)) removeAccount.mutate(a);
  };

  const coaData: any = coa.data ?? {};
  const mapData: any = mappingsQuery.data ?? {};
  const unmapped: any[] = unmappedQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Fiscal Chart of Accounts" description="Coretax L1-D Jasa fiscal chart with the commercial (HMM-Connect) to fiscal mapping used for fiscal reconciliation and SPT reporting."
        actions={<div className="flex gap-2"><Button variant="outline" disabled title="Fiscal COA is seeded from Coretax L1-D Jasa">Import</Button><Button variant="outline" onClick={() => exportCsv("fiscal-chart-of-accounts.csv", ["Code","Name","Category","Header","Status"], (coaData.items ?? []).map((i: any) => [i.code, i.name, i.category, i.is_header ? "Yes" : "No", i.is_active ? "Active" : "Archived"]))}>Export</Button></div>} />

      <div className="flex gap-2">
        {([["coa", "Chart of Accounts"], ["mapping", "Commercial Mapping"]] as const).map(([key, label]) => (
          <Button key={key} variant={tab === key ? "secondary" : "outline"} onClick={() => setTab(key)}>{label}</Button>
        ))}
      </div>

      {tab === "coa" ? <>
        <ModuleSummary metrics={[
          { label: "Fiscal Accounts", value: coaData.total ?? 0 },
          { label: "Posting Accounts", value: (coaData.items ?? []).filter((i: any) => !i.is_header).length, note: "Visible page" },
          { label: "Header Groups", value: (coaData.items ?? []).filter((i: any) => i.is_header).length, note: "Visible page" },
        ]} />
        <Card>
          <div className="mb-5 flex flex-wrap gap-3">
            <Input aria-label="Search fiscal accounts" className="max-w-sm" placeholder="Search code or name..." value={search} onChange={(e) => setSearch(e.target.value)} />
            <select className={selectClass + " max-w-44"} value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All categories</option>{((cats.data ?? []) as string[]).map((c) => <option key={c} value={c}>{c}</option>)}</select>
            <select className={selectClass + " max-w-40"} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option value="active">Active</option><option value="archived">Archived</option></select>
            <div className="ml-auto"><Button onClick={() => openForm()}><Plus size={16} /> Create</Button></div>
          </div>
          {coa.isLoading ? <div className="py-12"><Loading /></div> : <>
            <Table variant="grid"><THead><TR><TH>Code</TH><TH>Name</TH><TH>Category</TH><TH>Kind</TH><TH>Status</TH><TH>Actions</TH></TR></THead>
            <TBody>{ (coaData.items ?? []).map((a: FiscalAccount) => <TR key={a.id}><TD className="font-mono font-medium">{a.code}</TD><TD>{a.name}</TD><TD>{a.category}</TD><TD>{a.is_header ? <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium">Header</span> : <span className="rounded bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">Posting</span>}</TD><TD><span className={a.is_active ? "text-emerald-700" : "text-slate-500"}>{a.is_active ? "Active" : "Archived"}</span></TD><TD><div className="flex gap-1"><Button size="xs" variant="outline" onClick={() => setViewing(a)}><Eye size={15} /> View</Button><Button size="xs" variant="outline" onClick={() => openForm(a)}>Edit</Button><Button size="xs" variant="outline" onClick={() => confirmDelete(a)}><Trash2 size={14} /></Button></div></TD></TR>)}</TBody></Table>
            {!coaData.items?.length && <p className="py-8 text-center text-sm text-slate-500">No fiscal accounts found.</p>}
            <div className="mt-4 flex items-center justify-between text-sm"><span>{coaData.total ?? 0} accounts</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page} of {Math.max(coaData.pages ?? 1, 1)}</span><Button size="sm" variant="outline" disabled={page >= (coaData.pages ?? 1)} onClick={() => setPage(page + 1)}>Next</Button></div></div>
          </>}
        </Card>
      </> : <>
        <ModuleSummary metrics={[
          { label: "Active Mappings", value: mapData.total ?? 0 },
          { label: "Commercial Accounts Mapped", value: mapData.total ?? 0 },
          { label: "Commercial Accounts Total", value: "303", note: "Seeded chart" },
        ]} />
        <Card>
          <div className="mb-5 flex flex-wrap gap-3">
            <Input aria-label="Search mappings" className="max-w-sm" placeholder="Search fiscal or commercial account..." value={mSearch} onChange={(e) => setMSearch(e.target.value)} />
            <div className="ml-auto"><Button onClick={() => setAddOpen(true)}><Plus size={16} /> Add Mapping</Button></div>
          </div>
          {mappingsQuery.isLoading ? <div className="py-12"><Loading /></div> : <>
            <Table variant="grid"><THead><TR><TH>Commercial Account</TH><TH>Fiscal Account</TH><TH>Actions</TH></TR></THead>
            <TBody>{ (mapData.items ?? []).map((m: FiscalMapping) => <TR key={m.id}><TD className="font-mono">{m.commercial_code} <span className="ml-1 font-sans text-slate-600">{m.commercial_name}</span></TD><TD><span className="font-mono">{m.fiscal_code}</span> <span className="ml-1 text-slate-600">{m.fiscal_name}</span></TD><TD><Button size="xs" variant="outline" disabled={removeMapping.isPending} onClick={() => { if (window.confirm("Remove this mapping?")) removeMapping.mutate(m.id); }}><Trash2 size={14} /></Button></TD></TR>)}</TBody></Table>
            {!mapData.items?.length && <p className="py-8 text-center text-sm text-slate-500">No mappings found.</p>}
            <div className="mt-4 flex items-center justify-between text-sm"><span>{mapData.total ?? 0} mappings</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={mPage <= 1} onClick={() => setMPage(mPage - 1)}>Previous</Button><span>Page {mPage} of {Math.max(mapData.pages ?? 1, 1)}</span><Button size="sm" variant="outline" disabled={mPage >= (mapData.pages ?? 1)} onClick={() => setMPage(mPage + 1)}>Next</Button></div></div>
          </>}
        </Card>
      </>}

      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}><DialogContent><DialogHeader><DialogTitle>Fiscal Account</DialogTitle></DialogHeader>{viewing && <DialogBody className="space-y-5"><div className="grid gap-4 sm:grid-cols-2">{[["Code",viewing.code],["Name",viewing.name],["Category",viewing.category],["Kind",viewing.is_header ? "Header" : "Posting"],["Parent Code",viewing.parent_code ?? "—"],["Status",viewing.is_active ? "Active" : "Archived"],["Sort Order",String(viewing.sort_order)]].map(([label,value]) => <div key={label as string}><div className="text-xs font-medium uppercase text-slate-500">{label}</div><div className="mt-1">{value}</div></div>)}</div></DialogBody>}<DialogFooter><Button variant="outline" onClick={() => setViewing(null)}>Close</Button></DialogFooter></DialogContent></Dialog>

      <Dialog open={formOpen} onOpenChange={setFormOpen}><DialogContent><DialogHeader><DialogTitle className="text-lg font-semibold">{editing ? "Edit Fiscal Account" : "Create Fiscal Account"}</DialogTitle></DialogHeader><form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}><DialogBody className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Code<Input required maxLength={20} value={form.code ?? ""} disabled={!!editing} onChange={(e) => setForm({ ...form, code: e.target.value })} /></label>
        <label className="text-sm font-medium">Name<Input required maxLength={250} value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="text-sm font-medium">Category<Input required maxLength={60} value={form.category ?? ""} onChange={(e) => setForm({ ...form, category: e.target.value })} /></label>
        <label className="text-sm font-medium">Parent Code<Input maxLength={20} value={form.parent_code ?? ""} onChange={(e) => setForm({ ...form, parent_code: e.target.value || null })} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!form.is_header} onChange={(e) => setForm({ ...form, is_header: e.target.checked })} /> Header group</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active !== false} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>
      </DialogBody><DialogFooter><Button type="button" variant="outline" onClick={() => setFormOpen(false)}>Cancel</Button><Button type="submit" loading={save.isPending}>Save</Button></DialogFooter></form></DialogContent></Dialog>

      <Dialog open={addOpen} onOpenChange={setAddOpen}><DialogContent><DialogHeader><DialogTitle>Add Commercial-to-Fiscal Mapping</DialogTitle></DialogHeader><DialogBody className="grid gap-4">
        <label className="text-sm font-medium">Fiscal Account
          <select className={selectClass} value={addFiscalId} onChange={(e) => setAddFiscalId(e.target.value)}><option value="">Select fiscal account</option>{(opts.data?.items ?? []).map((a: any) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</select>
        </label>
        <label className="text-sm font-medium">Unmapped Commercial Account
          <Input placeholder="Search commercial accounts..." value={mappingSearch} onChange={(e) => setMappingSearch(e.target.value)} />
          <select className={selectClass + " mt-2"} value={pickFiscal} onChange={(e) => setPickFiscal(e.target.value)}><option value="">Select commercial account</option>{unmapped.map((c: any) => <option key={c.id} value={c.id}>{c.account_code} — {c.account_name}</option>)}</select>
          <span className="mt-1 block text-xs text-slate-500">{unmapped.length} available</span>
        </label>
      </DialogBody><DialogFooter><Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button><Button loading={addMapping.isPending} disabled={!addFiscalId || !pickFiscal} onClick={() => addMapping.mutate()}>Create Mapping</Button></DialogFooter></DialogContent></Dialog>
    </div>
  );
}
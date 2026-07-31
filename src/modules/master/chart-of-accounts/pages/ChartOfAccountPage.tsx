import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ChevronDown, ChevronRight, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { archiveAccount, createAccount, getAccountLookup, getAccounts, getAccountTree, updateAccount } from "../api";
import type { AccountPayload, AccountType, ChartOfAccount, ChartOfAccountNode, NormalBalance } from "../types";

const accountTypes: AccountType[] = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"];
const emptyForm: AccountPayload = { account_code: "", account_name: "", account_type: "ASSET", parent_account_id: null, normal_balance: "DEBIT", description: "", is_active: true };
const selectClass = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500";

function message(error: unknown) {
  if (!axios.isAxiosError(error)) return "Unable to complete the request.";
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join("; ");
  return "Unable to complete the request.";
}

function TreeRow({ node, depth = 0 }: { node: ChartOfAccountNode; depth?: number }) {
  const [open, setOpen] = useState(true);
  return <>
    <div className="flex items-center gap-2 border-b border-slate-100 py-2 text-sm" style={{ paddingLeft: `${depth * 24}px` }}>
      {node.children.length ? <button type="button" onClick={() => setOpen(!open)}>{open ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}</button> : <span className="w-4"/>}
      <span className="w-28 font-mono font-medium">{node.account_code}</span>
      <span className="flex-1">{node.account_name}</span>
      <span className="text-xs text-slate-500">{node.account_type}</span>
      {!node.is_active && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">Archived</span>}
    </div>
    {open && node.children.map((child) => <TreeRow key={child.id} node={child} depth={depth + 1}/>)}
  </>;
}

export default function ChartOfAccountPage() {
  const client = useQueryClient();
  const [page, setPage] = useState(1), [search, setSearch] = useState("");
  const [type, setType] = useState<AccountType | "">(""), [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("account_code"), [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [view, setView] = useState<"table" | "tree">("table"), [editing, setEditing] = useState<ChartOfAccount | null>(null);
  const [formOpen, setFormOpen] = useState(false), [form, setForm] = useState<AccountPayload>(emptyForm);
  const pageSize = 20;

  useEffect(() => setPage(1), [search, type, status]);
  const params = { page, page_size: pageSize, search: search || undefined, account_type: type || undefined,
    is_active: status === "active" ? true : status === "archived" ? false : undefined, sort_by: sortBy, sort_order: sortOrder };
  const accounts = useQuery({ queryKey: ["chart-of-accounts", params], queryFn: () => getAccounts(params), enabled: view === "table" });
  const tree = useQuery({ queryKey: ["chart-of-accounts-tree"], queryFn: getAccountTree, enabled: view === "tree" });
  const lookup = useQuery({ queryKey: ["chart-of-accounts-lookup"], queryFn: getAccountLookup });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["chart-of-accounts"] });
    client.invalidateQueries({ queryKey: ["chart-of-accounts-tree"] });
    client.invalidateQueries({ queryKey: ["chart-of-accounts-lookup"] });
  };
  const save = useMutation({ mutationFn: () => editing ? updateAccount(editing.id, form) : createAccount(form), onSuccess: () => { toast.success(`Account ${editing ? "updated" : "created"}.`); setFormOpen(false); refresh(); }, onError: (e) => toast.error(message(e)) });
  const archive = useMutation({ mutationFn: archiveAccount, onSuccess: () => { toast.success("Account archived."); refresh(); }, onError: (e) => toast.error(message(e)) });
  const restore = useMutation({ mutationFn: (id: number) => updateAccount(id, { is_active: true }), onSuccess: () => { toast.success("Account restored."); refresh(); }, onError: (e) => toast.error(message(e)) });

  function openForm(account?: ChartOfAccount) {
    setEditing(account ?? null);
    setForm(account ? { account_code: account.account_code, account_name: account.account_name, account_type: account.account_type, parent_account_id: account.parent_account_id, normal_balance: account.normal_balance, description: account.description ?? "", is_active: account.is_active } : emptyForm);
    setFormOpen(true);
  }
  function sort(field: string) { if (sortBy === field) setSortOrder(sortOrder === "asc" ? "desc" : "asc"); else { setSortBy(field); setSortOrder("asc"); } }

  return <>
    <div className="space-y-6">
      <PageHeader title="Chart of Accounts" description="Manage the finance account structure and availability." actions={<Button onClick={() => openForm()}><Plus size={16}/> Add Account</Button>}/>
      <Card>
        <div className="mb-5 flex flex-wrap gap-3">
          <Input aria-label="Search accounts" className="max-w-sm" placeholder="Search code, name, or description..." value={search} onChange={(e) => setSearch(e.target.value)}/>
          <select className={selectClass + " max-w-48"} value={type} onChange={(e) => setType(e.target.value as AccountType | "")}><option value="">All account types</option>{accountTypes.map((v) => <option key={v}>{v}</option>)}</select>
          <select className={selectClass + " max-w-40"} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option value="active">Active</option><option value="archived">Archived</option></select>
          <div className="ml-auto flex"><Button variant={view === "table" ? "secondary" : "outline"} onClick={() => setView("table")}>Table View</Button><Button variant={view === "tree" ? "secondary" : "outline"} onClick={() => setView("tree")}>Hierarchy View</Button></div>
        </div>
        {(accounts.isLoading || tree.isLoading) ? <div className="py-12"><Loading/></div> : view === "tree" ?
          <div className="rounded-lg border border-slate-200 px-4">{tree.data?.map((node) => <TreeRow key={node.id} node={node}/>)}</div> :
          <><Table><THead><TR>{[["account_code","Account Code"],["account_name","Account Name"],["account_type","Account Type"],["normal_balance","Normal Balance"],["is_active","Status"]].map(([field,label]) => <TH key={field}><button onClick={() => sort(field)}>{label}{sortBy === field ? (sortOrder === "asc" ? " ↑" : " ↓") : ""}</button></TH>)}<TH>Parent Account</TH><TH>Actions</TH></TR></THead>
          <TBody>{accounts.data?.items.map((account) => <TR key={account.id}><TD className="font-mono font-medium">{account.account_code}</TD><TD>{account.account_name}</TD><TD>{account.account_type}</TD><TD>{account.normal_balance}</TD><TD><span className={account.is_active ? "text-emerald-700" : "text-slate-500"}>{account.is_active ? "Active" : "Archived"}</span></TD><TD>{lookup.data?.find((p) => p.id === account.parent_account_id)?.account_name ?? "—"}</TD><TD><div className="flex gap-1"><Button size="xs" variant="ghost" title="Edit" onClick={() => openForm(account)}><Pencil size={15}/></Button>{account.is_active ? <Button size="xs" variant="ghost" title="Archive" onClick={() => window.confirm(`Archive ${account.account_name}?`) && archive.mutate(account.id)}><Trash2 size={15}/></Button> : <Button size="xs" variant="ghost" title="Restore" onClick={() => restore.mutate(account.id)}><RotateCcw size={15}/></Button>}</div></TD></TR>)}</TBody></Table>
          {!accounts.data?.items.length && <p className="py-8 text-center text-sm text-slate-500">No accounts found.</p>}
          <div className="mt-4 flex items-center justify-between text-sm"><span>{accounts.data?.total_items ?? 0} accounts</span><div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page} of {Math.max(accounts.data?.total_pages ?? 1, 1)}</span><Button size="sm" variant="outline" disabled={page >= (accounts.data?.total_pages ?? 1)} onClick={() => setPage(page + 1)}>Next</Button></div></div></>}
      </Card>
    </div>
    <Dialog open={formOpen} onOpenChange={setFormOpen}><DialogContent><DialogHeader><DialogTitle className="text-lg font-semibold">{editing ? "Edit Account" : "Create Account"}</DialogTitle></DialogHeader><form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}><DialogBody className="grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium">Account Code<Input required maxLength={30} value={form.account_code} onChange={(e) => setForm({...form, account_code: e.target.value})}/></label>
      <label className="text-sm font-medium">Account Name<Input required maxLength={150} value={form.account_name} onChange={(e) => setForm({...form, account_name: e.target.value})}/></label>
      <label className="text-sm font-medium">Account Type<select className={selectClass} value={form.account_type} onChange={(e) => setForm({...form, account_type: e.target.value as AccountType})}>{accountTypes.map((v) => <option key={v}>{v}</option>)}</select></label>
      <label className="text-sm font-medium">Normal Balance<select className={selectClass} value={form.normal_balance} onChange={(e) => setForm({...form, normal_balance: e.target.value as NormalBalance})}><option>DEBIT</option><option>CREDIT</option></select></label>
      <label className="text-sm font-medium sm:col-span-2">Parent Account<select className={selectClass} value={form.parent_account_id ?? ""} onChange={(e) => setForm({...form, parent_account_id: e.target.value ? Number(e.target.value) : null})}><option value="">No parent account</option>{lookup.data?.filter((item) => item.id !== editing?.id).map((item) => <option key={item.id} value={item.id}>{item.account_code} — {item.account_name}</option>)}</select></label>
      <label className="text-sm font-medium sm:col-span-2">Description<textarea className={selectClass + " h-24 py-2"} maxLength={500} value={form.description ?? ""} onChange={(e) => setForm({...form, description: e.target.value})}/></label>
      <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({...form, is_active: e.target.checked})}/> Active</label>
    </DialogBody><DialogFooter><Button type="button" variant="outline" onClick={() => setFormOpen(false)}>Cancel</Button><Button type="submit" loading={save.isPending}>Save Account</Button></DialogFooter></form></DialogContent></Dialog>
  </>;
}

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ChevronDown, ChevronRight, Eye, Plus } from "lucide-react";
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
import { archiveAccount, createAccount, getAccountLookup, getAccounts, getAccountTree, restoreAccount, updateAccount } from "../api";
import type { AccountPayload, AccountType, ChartOfAccount, ChartOfAccountNode, NormalBalance } from "../types";

const accountTypes: AccountType[] = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"];
const emptyForm: AccountPayload = { account_code: "", account_name: "", account_type: "ASSET", parent_account_id: null, normal_balance: "DEBIT", description: "", cash_flow_category: null, is_posting: true, is_active: true };
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
      <span className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">{node.is_posting ? "Posting" : "Group"}</span>
      {node.is_system && <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">System</span>}
      {!node.is_active && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">Archived</span>}
    </div>
    {open && node.children.map((child) => <TreeRow key={child.id} node={child} depth={depth + 1}/>)}
  </>;
}

export default function ChartOfAccountPage() {
  const client = useQueryClient();
  const [page, setPage] = useState(1), [search, setSearch] = useState("");
  const [type, setType] = useState<AccountType | "">(""), [balance, setBalance] = useState<NormalBalance | "">(""), [posting, setPosting] = useState(""), [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("account_code"), [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [view, setView] = useState<"table" | "tree">("table"), [editing, setEditing] = useState<ChartOfAccount | null>(null), [viewing, setViewing] = useState<ChartOfAccount | null>(null);
  const [formOpen, setFormOpen] = useState(false), [form, setForm] = useState<AccountPayload>(emptyForm);
  const pageSize = 20;

  useEffect(() => setPage(1), [search, type, balance, posting, status]);
  const params = { page, page_size: pageSize, search: search || undefined, account_type: type || undefined,
    normal_balance: balance || undefined, is_posting: posting === "posting" ? true : posting === "group" ? false : undefined,
    is_active: status === "active" ? true : status === "archived" ? false : undefined, sort_by: sortBy, sort_order: sortOrder };
  const accounts = useQuery({ queryKey: ["chart-of-accounts", params], queryFn: () => getAccounts(params), enabled: view === "table" });
  const tree = useQuery({ queryKey: ["chart-of-accounts-tree"], queryFn: getAccountTree });
  const lookup = useQuery({ queryKey: ["chart-of-accounts-lookup"], queryFn: () => getAccountLookup({is_posting:false, is_active:true}) });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["chart-of-accounts"] });
    client.invalidateQueries({ queryKey: ["chart-of-accounts-tree"] });
    client.invalidateQueries({ queryKey: ["chart-of-accounts-lookup"] });
  };
  const save = useMutation({ mutationFn: () => editing ? updateAccount(editing.id, form) : createAccount(form), onSuccess: () => { toast.success(`Account ${editing ? "updated" : "created"}.`); setFormOpen(false); refresh(); }, onError: (e) => toast.error(message(e)) });
  const activeMutation = useMutation({ mutationFn: (account: ChartOfAccount) => account.is_active ? archiveAccount(account.id) : restoreAccount(account.id), onSuccess: (_, account) => { toast.success(`Account ${account.is_active ? "archived" : "restored"}.`); refresh(); }, onError: (e) => toast.error(message(e)) });

  const descendants = (accountId?: number) => {
    const excluded = new Set<number>();
    const visit = (nodes: ChartOfAccountNode[]) => nodes.forEach((node) => { if (excluded.has(node.parent_account_id ?? -1) || node.id === accountId) excluded.add(node.id); visit(node.children); });
    if (accountId) visit(tree.data ?? []);
    return excluded;
  };

  function openForm(account?: ChartOfAccount) {
    setEditing(account ?? null);
    setForm(account ? { account_code: account.account_code, account_name: account.account_name, account_type: account.account_type, parent_account_id: account.parent_account_id, normal_balance: account.normal_balance, description: account.description ?? "", cash_flow_category: account.cash_flow_category, is_posting: account.is_posting, is_active: account.is_active } : {...emptyForm});
    setFormOpen(true);
  }
  function sort(field: string) { if (sortBy === field) setSortOrder(sortOrder === "asc" ? "desc" : "asc"); else { setSortBy(field); setSortOrder("asc"); } }

  return <>
    <div className="space-y-6">
      <PageHeader title="Chart of Accounts" description="Manage the finance account structure and availability." actions={<div className="flex flex-wrap gap-2"><Button onClick={() => openForm()}><Plus size={16}/> Create</Button><Button variant="outline" disabled title="COA import is not available yet">Import</Button><Button variant="outline" onClick={() => exportCsv("chart-of-accounts.csv", ["Code","Name","Type","Normal Balance","Posting","Status"], (accounts.data?.items ?? []).map((item) => [item.account_code,item.account_name,item.account_type,item.normal_balance,item.is_posting ? "Yes" : "No",item.is_active ? "Active" : "Archived"]))}>Export</Button></div>}/>
      <ModuleSummary metrics={[
        {label:"Total Accounts",value:accounts.data?.total_items ?? lookup.data?.length ?? 0},
        {label:"Active Accounts",value:accounts.data?.items.filter((item) => item.is_active).length ?? 0,note:"Visible page"},
        {label:"Posting Accounts",value:accounts.data?.items.filter((item) => item.is_posting).length ?? 0,note:"Visible page"},
        {label:"System Accounts",value:accounts.data?.items.filter((item) => item.is_system).length ?? 0,note:"Visible page"},
      ]}/>
      <Card>
        <div className="mb-5 flex flex-wrap gap-3">
          <Input aria-label="Search accounts" className="max-w-sm" placeholder="Search code, name, or description..." value={search} onChange={(e) => setSearch(e.target.value)}/>
          <select className={selectClass + " max-w-48"} value={type} onChange={(e) => setType(e.target.value as AccountType | "")}><option value="">All account types</option>{accountTypes.map((v) => <option key={v}>{v}</option>)}</select>
          <select className={selectClass + " max-w-44"} value={balance} onChange={(e) => setBalance(e.target.value as NormalBalance | "")}><option value="">All balances</option><option>DEBIT</option><option>CREDIT</option></select>
          <select aria-label="Posting account filter" className={selectClass + " max-w-44"} value={posting} onChange={(e) => setPosting(e.target.value)}><option value="">All accounts</option><option value="posting">Posting accounts</option><option value="group">Group accounts</option></select>
          <select className={selectClass + " max-w-40"} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option value="active">Active</option><option value="archived">Archived</option></select>
          <div className="ml-auto flex"><Button variant={view === "table" ? "secondary" : "outline"} onClick={() => setView("table")}>Table View</Button><Button variant={view === "tree" ? "secondary" : "outline"} onClick={() => setView("tree")}>Hierarchy View</Button></div>
        </div>
        {(accounts.isLoading || tree.isLoading) ? <div className="py-12"><Loading/></div> : view === "tree" ?
          <div className="rounded-lg border border-slate-200 px-4">{tree.data?.map((node) => <TreeRow key={node.id} node={node}/>)}</div> :
          <><Table><THead><TR>{[["account_code","Account Code"],["account_name","Account Name"],["account_type","Account Type"]].map(([field,label]) => <TH key={field}><button onClick={() => sort(field)}>{label}{sortBy === field ? (sortOrder === "asc" ? " ↑" : " ↓") : ""}</button></TH>)}<TH>Parent Account</TH><TH><button onClick={() => sort("normal_balance")}>Normal Balance{sortBy === "normal_balance" ? (sortOrder === "asc" ? " ↑" : " ↓") : ""}</button></TH><TH>Posting Account</TH><TH>Cash Flow Category</TH><TH>Status</TH><TH>Actions</TH></TR></THead>
          <TBody>{accounts.data?.items.map((account) => <TR key={account.id}><TD className="font-mono font-medium">{account.account_code}</TD><TD>{account.account_name}</TD><TD>{account.account_type}</TD><TD>{lookup.data?.find((p) => p.id === account.parent_account_id)?.account_name ?? "—"}</TD><TD>{account.normal_balance}</TD><TD>{account.is_posting ? "Yes" : "No"}</TD><TD>{account.cash_flow_category ?? "—"}</TD><TD><span className={account.is_active ? "text-emerald-700" : "text-slate-500"}>{account.is_active ? "Active" : "Archived"}</span></TD><TD><div className="flex gap-1"><Button size="xs" variant="outline" onClick={() => setViewing(account)}><Eye size={15}/> View</Button><Button size="xs" variant="outline" onClick={() => openForm(account)}>Edit</Button>{!account.is_system && <Button size="xs" variant="outline" disabled={activeMutation.isPending} onClick={() => activeMutation.mutate(account)}>{account.is_active ? "Archive" : "Restore"}</Button>}</div></TD></TR>)}</TBody></Table>
          {!accounts.data?.items.length && <p className="py-8 text-center text-sm text-slate-500">No accounts found.</p>}
          <div className="mt-4 flex items-center justify-between text-sm"><span>{accounts.data?.total_items ?? 0} accounts</span><div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page} of {Math.max(accounts.data?.total_pages ?? 1, 1)}</span><Button size="sm" variant="outline" disabled={page >= (accounts.data?.total_pages ?? 1)} onClick={() => setPage(page + 1)}>Next</Button></div></div></>}
      </Card>
    </div>
    <Dialog open={!!viewing} onOpenChange={(open) => !open && setViewing(null)}><DialogContent><DialogHeader><DialogTitle>Account Workspace</DialogTitle></DialogHeader>{viewing && <DialogBody className="space-y-5"><div className="grid gap-4 sm:grid-cols-2">{[["Account Code",viewing.account_code],["Account Name",viewing.account_name],["Type",viewing.account_type],["Normal Balance",viewing.normal_balance],["Posting",viewing.is_posting ? "Yes" : "No"],["Status",viewing.is_active ? "Active" : "Archived"],["Cash Flow",viewing.cash_flow_category ?? "—"],["Description",viewing.description ?? "—"]].map(([label,value]) => <div key={label}><div className="text-xs font-medium uppercase text-slate-500">{label}</div><div className="mt-1">{value}</div></div>)}</div></DialogBody>}<DialogFooter><Button variant="outline" onClick={() => setViewing(null)}>Close</Button>{viewing && <Button onClick={() => {const account=viewing; setViewing(null); openForm(account);}}>Edit</Button>}</DialogFooter></DialogContent></Dialog>
    <Dialog open={formOpen} onOpenChange={setFormOpen}><DialogContent><DialogHeader><DialogTitle className="text-lg font-semibold">{editing ? "Edit Account" : "Create Account"}</DialogTitle></DialogHeader><form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}><DialogBody className="grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium">Account Code<Input required maxLength={30} value={form.account_code} onChange={(e) => setForm({...form, account_code: e.target.value})}/></label>
      <label className="text-sm font-medium">Account Name<Input required maxLength={150} value={form.account_name} onChange={(e) => setForm({...form, account_name: e.target.value})}/></label>
      <label className="text-sm font-medium">Account Type<select className={selectClass} value={form.account_type} onChange={(e) => {const account_type=e.target.value as AccountType; setForm({...form, account_type, normal_balance: account_type === "ASSET" || account_type === "EXPENSE" ? "DEBIT" : "CREDIT"});}}>{accountTypes.map((v) => <option key={v}>{v}</option>)}</select></label>
      <label className="text-sm font-medium">Normal Balance<select className={selectClass} value={form.normal_balance} onChange={(e) => setForm({...form, normal_balance: e.target.value as NormalBalance})}><option>DEBIT</option><option>CREDIT</option></select></label>
      <label className="text-sm font-medium sm:col-span-2">Parent Account<select className={selectClass} value={form.parent_account_id ?? ""} onChange={(e) => setForm({...form, parent_account_id: e.target.value ? Number(e.target.value) : null})}><option value="">No parent account</option>{lookup.data?.filter((item) => !descendants(editing?.id).has(item.id)).map((item) => <option key={item.id} value={item.id}>{item.account_code} — {item.account_name}</option>)}</select></label>
      <label className="text-sm font-medium sm:col-span-2">Description<textarea className={selectClass + " h-24 py-2"} maxLength={500} value={form.description ?? ""} onChange={(e) => setForm({...form, description: e.target.value})}/></label>
      <label className="text-sm font-medium sm:col-span-2">Cash Flow Category<Input maxLength={30} value={form.cash_flow_category ?? ""} onChange={(e) => setForm({...form, cash_flow_category: e.target.value || null})}/></label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_posting} onChange={(e) => setForm({...form, is_posting: e.target.checked})}/> Posting Account</label>
      <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({...form, is_active: e.target.checked})}/> Active</label>
    </DialogBody><DialogFooter><Button type="button" variant="outline" onClick={() => setFormOpen(false)}>Cancel</Button><Button type="submit" loading={save.isPending}>Save Account</Button></DialogFooter></form></DialogContent></Dialog>
  </>;
}

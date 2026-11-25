import { Printer } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import DataWorkspace, { WorkspaceFilters } from "@/components/workspace/DataWorkspace";
import Button from "@/components/ui/Button";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import Pagination from "@/components/datatable/Pagination";
import { FORM_UI } from "@/config/formUi";
import { apiErrorMessage } from "@/utils/apiError";
import { createReconciliation, getReconciliationAccounts, listReconciliations, type Reconciliation, type ReconciliationStatus } from "./api";

const today=new Date().toISOString().slice(0,10);
const money=(v:number|string|null|undefined)=>Number(v||0).toLocaleString("id-ID");
const input=`${FORM_UI.controlBase} ${FORM_UI.density[FORM_UI.defaultDensity].control}`;
const STATUSES: ReconciliationStatus[]=["DRAFT","IN_PROGRESS","COMPLETED","VOID"];
const statusVariant: Record<ReconciliationStatus, BadgeVariant>={DRAFT:"warning",IN_PROGRESS:"warning",COMPLETED:"success",VOID:"danger"};

type ReconciliationFilters={page:number;page_size:number;status:string;account_id:string;search:string};
type ReconciliationForm={
  account_id: string;
  statement_start_date: string;
  statement_end_date: string;
  statement_opening_balance: string;
  statement_closing_balance: string;
  notes: string;
};

export default function BankReconciliationListPage(){
  const nav=useNavigate(),qc=useQueryClient();
  const [filters,setFilters]=useState<ReconciliationFilters>({page:1,page_size:20,status:"",account_id:"",search:""});
  const [open,setOpen]=useState(false);
  const [form,setForm]=useState<ReconciliationForm>({account_id:"",statement_start_date:today,statement_end_date:today,statement_opening_balance:"0",statement_closing_balance:"0",notes:""});
  const q=useQuery({queryKey:["bank-reconciliations",filters],queryFn:()=>listReconciliations(filters)});
  const accounts=useQuery({queryKey:["reconciliation-accounts"],queryFn:getReconciliationAccounts});
  const create=useMutation({mutationFn:()=>createReconciliation({...form,account_id:Number(form.account_id)}),onSuccess:x=>{qc.invalidateQueries({queryKey:["bank-reconciliations"]});nav(`/bank-reconciliations/${x.id}`)},onError:()=>toast.error("Reconciliation could not be created")});
  const rows: Reconciliation[]=q.data?.items??[];
  const account=accounts.data?.find(a=>String(a.id)===String(filters.account_id));
  const filterContext=`${account?`${account.account_code} — ${account.account_name}`:"All bank accounts"} · ${filters.status||"All statuses"} · ${filters.search||"All reconciliations"} · page ${filters.page}`;
  const count=(status:ReconciliationStatus)=>rows.filter(row=>row.status===status).length;
  return <DataWorkspace area="Finance">
    <div className="space-y-4">
      <PageHeader title="Bank Reconciliation" description="Compare posted bank activity with imported statement transactions." actions={<>
        <Button onClick={()=>setOpen(true)}>New Reconciliation</Button>
        <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
      </>}/>
      <ModuleSummary metrics={[
        {label:"Total reconciliations",value:q.data?.total_items??0,note:"Matching the current filters"},
        {label:"On this page",value:rows.length},
        {label:"Completed",value:count("COMPLETED"),note:"On this page"},
        {label:"In progress",value:count("IN_PROGRESS"),note:"On this page"},
        {label:"Draft",value:count("DRAFT"),note:"On this page"},
        {label:"Void",value:count("VOID"),note:"On this page"},
      ]}/>
      {/* WorkspaceFilters supplies the aria-label="Filters" toggle; values stay visible in the context line. */}
      <WorkspaceFilters label="Filters" context={filterContext}>
        <div className="grid gap-2 md:grid-cols-4">
          <select aria-label="Bank account" className={input} value={filters.account_id} onChange={e=>setFilters({...filters,account_id:e.target.value,page:1})}><option value="">All bank accounts</option>{accounts.data?.map(a=><option key={a.id} value={a.id}>{a.account_code} — {a.account_name}</option>)}</select>
          <select aria-label="Status" className={input} value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value,page:1})}><option value="">All statuses</option>{STATUSES.map(x=><option key={x}>{x}</option>)}</select>
          <input aria-label="Search number or account" className={input} placeholder="Search number or account" value={filters.search} onChange={e=>setFilters({...filters,search:e.target.value,page:1})}/>
        </div>
      </WorkspaceFilters>
      {accounts.isLoading||q.isLoading
        ? <Loading message="Loading bank reconciliations…" />
        : accounts.isError||q.isError
         ? <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
             <p>Bank reconciliations could not be loaded.</p>
             {q.isError&&<p>{apiErrorMessage(q.error,"Please try again.")}</p>}
             {accounts.isError&&<p>{apiErrorMessage(accounts.error,"Bank accounts could not be loaded.")}</p>}
           </div>
         : rows.length===0
          ? <Empty title="No reconciliations for these filters." description="Adjust the filters or create a new reconciliation to get started." />
          : <>
            <Table variant="grid" stickyHeader><THead><TR><TH>Reconciliation</TH><TH>Bank Account</TH><TH>Statement Period</TH><TH className="text-right">Statement Closing</TH><TH className="text-right">System Closing</TH><TH className="text-right">Difference</TH><TH className="text-center">Matched</TH><TH className="text-center">Unmatched</TH><TH>Status</TH><TH>Actions</TH></TR></THead><TBody>{rows.map(x=><TR key={x.id}><TD>{x.reconciliation_number}</TD><TD>{x.account_code} — {x.account_name}</TD><TD>{x.statement_start_date} – {x.statement_end_date}</TD><TD className="text-right tabular-nums">{money(x.statement_closing_balance)}</TD><TD className="text-right tabular-nums">{money(x.system_closing_balance)}</TD><TD className="text-right tabular-nums">{money(x.difference)}</TD><TD className="text-center">{x.matched_count}</TD><TD className="text-center">{x.unmatched_count}</TD><TD><Badge variant={statusVariant[x.status]??"warning"}>{x.status}</Badge></TD><TD><Button size="xs" variant="outline" onClick={()=>nav(`/bank-reconciliations/${x.id}`)}>View</Button></TD></TR>)}</TBody></Table>
            <Pagination page={filters.page} pages={Math.max(q.data?.total_pages??1,1)} total={q.data?.total_items} pageSize={filters.page_size} noun="reconciliations" onChange={page=>setFilters(current=>({...current,page}))}/>
          </>}
      {open&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40"><Card className="w-[min(92vw,620px)] p-4"><h2 className="mb-3 font-semibold">New Reconciliation</h2><div className="grid gap-3 sm:grid-cols-2"><label>Bank Account<select className={input} value={form.account_id} onChange={e=>setForm({...form,account_id:e.target.value})}><option value="">Select bank</option>{accounts.data?.map(a=><option key={a.id} value={a.id}>{a.account_code} — {a.account_name}</option>)}</select></label><label>Start Date<input className={input} type="date" value={form.statement_start_date} onChange={e=>setForm({...form,statement_start_date:e.target.value})}/></label><label>End Date<input className={input} type="date" value={form.statement_end_date} onChange={e=>setForm({...form,statement_end_date:e.target.value})}/></label><label>Opening Balance<input className={input} type="number" value={form.statement_opening_balance} onChange={e=>setForm({...form,statement_opening_balance:e.target.value})}/></label><label>Closing Balance<input className={input} type="number" value={form.statement_closing_balance} onChange={e=>setForm({...form,statement_closing_balance:e.target.value})}/></label><label>Notes<input className={input} value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label></div><div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={()=>setOpen(false)}>Cancel</Button><Button disabled={!form.account_id} onClick={()=>create.mutate()}>Save</Button></div></Card></div>}
    </div>
  </DataWorkspace>;
}

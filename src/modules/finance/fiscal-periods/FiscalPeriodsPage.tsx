import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import api from "@/api/client";

type FiscalPeriod = {
  id:number;
  fiscal_year:number;
  fiscal_month:number;
  period_name:string;
  start_date:string;
  end_date:string;
  is_open:boolean;
  is_closed:boolean;
};

const currentYear = new Date().getFullYear();
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function FiscalPeriodsPage(){
  const qc=useQueryClient();
  const [year,setYear]=useState(currentYear);
  const periods=useQuery({
    queryKey:["fiscal-periods",year],
    queryFn:async()=>(await api.get<FiscalPeriod[]>("/fiscal-periods",{params:{fiscal_year:year}})).data,
  });
  const initialized=(periods.data?.length??0)>0;
  const openCount=useMemo(()=>periods.data?.filter(row=>row.is_open&&!row.is_closed).length??0,[periods.data]);

  const initialize=useMutation({
    mutationFn:async()=> (await api.post("/fiscal-periods/initialize-year",{fiscal_year:year})).data,
    onSuccess:(data:any)=>{toast.success(data.message||`Fiscal year ${year} initialized`);qc.invalidateQueries({queryKey:["fiscal-periods",year]})},
    onError:(error:any)=>toast.error(error.response?.data?.detail||"Fiscal year could not be initialized"),
  });
  const closePeriod=useMutation({
    mutationFn:async(id:number)=>(await api.post(`/fiscal-periods/${id}/close`)).data,
    onSuccess:()=>{toast.success("Fiscal period closed");qc.invalidateQueries({queryKey:["fiscal-periods",year]})},
    onError:(error:any)=>toast.error(error.response?.data?.detail||"Fiscal period could not be closed"),
  });
  const reopenPeriod=useMutation({
    mutationFn:async({id,reason}:{id:number;reason:string})=>(await api.post(`/fiscal-periods/${id}/open`,{reason})).data,
    onSuccess:()=>{toast.success("Fiscal period reopened");qc.invalidateQueries({queryKey:["fiscal-periods",year]})},
    onError:(error:any)=>toast.error(error.response?.data?.detail||"Fiscal period could not be reopened"),
  });

  const reopen=(period:FiscalPeriod)=>{
    const reason=window.prompt(`Reason for reopening ${period.period_name}:`)?.trim();
    if(!reason)return;
    if(reason.length<3)return toast.error("Reopen reason must be at least 3 characters");
    reopenPeriod.mutate({id:period.id,reason});
  };

  return <div className="space-y-5">
    <PageHeader title="Fiscal Periods" description="Initialize monthly accounting periods, close completed months, and reopen a closed period only with an auditable reason." actions={<div className="flex items-center gap-2"><input className={`${input} w-28`} type="number" min={2000} max={2100} value={year} onChange={event=>setYear(Number(event.target.value)||currentYear)}/><Button disabled={initialize.isPending} onClick={()=>initialize.mutate()}>{initialized?"Complete Missing Periods":"Initialize Fiscal Year"}</Button></div>}/>

    {!initialized&&<Card className="border-amber-200 bg-amber-50 p-5"><div className="font-semibold text-amber-900">Fiscal year {year} is not initialized</div><p className="mt-1 text-sm text-amber-800">Accounting documents dated in {year} cannot post to the General Ledger until a matching open fiscal period exists. Initialize the year to create January through December automatically.</p></Card>}

    <div className="grid gap-3 sm:grid-cols-3">
      <Card className="p-4"><div className="text-xs uppercase text-slate-500">Fiscal Year</div><div className="mt-1 text-xl font-semibold">{year}</div></Card>
      <Card className="p-4"><div className="text-xs uppercase text-slate-500">Configured Periods</div><div className="mt-1 text-xl font-semibold">{periods.data?.length??0} / 12</div></Card>
      <Card className="p-4"><div className="text-xs uppercase text-slate-500">Open Periods</div><div className="mt-1 text-xl font-semibold">{openCount}</div></Card>
    </div>

    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[850px] text-sm">
        <thead><tr className="border-b text-left"><th className="p-3">Period</th><th>Start Date</th><th>End Date</th><th>Status</th><th className="text-right">Action</th></tr></thead>
        <tbody>{periods.isLoading?<tr><td className="p-8 text-center text-slate-500" colSpan={5}>Loading fiscal periods…</td></tr>:!periods.data?.length?<tr><td className="p-8 text-center text-slate-500" colSpan={5}>No fiscal periods configured for {year}.</td></tr>:periods.data.map(period=>{const open=period.is_open&&!period.is_closed;return <tr key={period.id} className="border-b"><td className="p-3 font-medium">{period.period_name}</td><td>{period.start_date}</td><td>{period.end_date}</td><td><Badge variant={open?"success":"warning"}>{open?"OPEN":"CLOSED"}</Badge></td><td className="text-right">{open?<Button size="sm" variant="outline" disabled={closePeriod.isPending} onClick={()=>{if(window.confirm(`Close ${period.period_name}? Posting into this period will be blocked.`))closePeriod.mutate(period.id)}}>Close Period</Button>:<Button size="sm" variant="outline" disabled={reopenPeriod.isPending} onClick={()=>reopen(period)}>Reopen</Button>}</td></tr>})}</tbody>
      </table>
    </Card>
    <p className="text-xs text-slate-500">Administrators and Finance users may manage periods. Reopening requires a reason and is recorded in the audit trail. Closed periods are never bypassed automatically.</p>
  </div>;
}

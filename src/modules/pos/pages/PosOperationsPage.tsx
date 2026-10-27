import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import SearchableSelect from "@/components/form/SearchableSelect";
import useAuthStore from "@/store/auth";
import { posApi } from "../api";
import OutletSetup from "../OutletSetup";
import { hotelOutletContext } from "../outletContext";
import { operationsApi, type OrderMode, type OutletTable, type Shift } from "../operationsApi";

const input="h-9 rounded border border-slate-300 bg-white px-2 text-sm";
const today=()=>new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Jakarta"}).format(new Date());
const money=(v:unknown)=>Number(v??0).toLocaleString("id-ID",{style:"currency",currency:"IDR"});
const errorMessage=(e:any)=>typeof e?.response?.data?.detail==="string"?e.response.data.detail:e?.message||"Action failed";

export default function PosOperationsPage(){
  const [params,setParams]=useSearchParams();
  const client=useQueryClient();
  const user=useAuthStore(s=>s.user);
  const manage=useAuthStore(s=>s.hasPermission("finance.manage"));
  const admin=useAuthStore(s=>s.hasPermission("admin.settings.manage"));
  const sell=useAuthStore(s=>s.hasPermission("pos.sell"));
  const [location,setLocation]=useState<number|undefined>(Number(params.get("location"))||undefined);
  const [department,setDepartment]=useState<number|undefined>(Number(params.get("outlet"))||undefined);
  const [tab,setTab]=useState("Orders");
  const [error,setError]=useState("");
  const [mode,setMode]=useState<OrderMode|undefined>();
  const [table,setTable]=useState<OutletTable|null>(null);
  const [tableName,setTableName]=useState("");
  const [seats,setSeats]=useState("2");
  const [opening,setOpening]=useState("");
  const [closing,setClosing]=useState<Shift|null>(null);
  const [counted,setCounted]=useState("");
  const [reason,setReason]=useState("");
  const [from,setFrom]=useState(today());const [to,setTo]=useState(today());
  const [cashier,setCashier]=useState("");
  const options=useQuery({queryKey:["pos-options",user?.id],queryFn:async()=>(await posApi.options()).data});
  const selection=hotelOutletContext(options.data,location,department);
  const {locations,departments}=selection;
  const scope={location_id:selection.location?.id??0,department_id:selection.department?.id??0};
  const context=useQuery({queryKey:["pos-operations",user?.id,location,department],queryFn:async()=>(await operationsApi.context(scope)).data,enabled:selection.valid,refetchInterval:15000});
  const report=useQuery({queryKey:["pos-outlet-report",user?.id,location,department,from,to,cashier],queryFn:async()=>(await operationsApi.report(scope,from,to,cashier?Number(cashier):undefined)).data,enabled:Boolean(selection.valid&&tab==="Reports"&&from&&to&&to>=from)});
  const refresh=()=>{void client.invalidateQueries({queryKey:["pos-options"]});void client.invalidateQueries({queryKey:["pos-operations"]});void client.invalidateQueries({queryKey:["pos-outlet-report"]});};
  const action=useMutation({mutationFn:async(fn:()=>Promise<unknown>)=>fn(),onSuccess:()=>{setError("");setClosing(null);setCounted("");setReason("");setOpening("");setTable(null);setTableName("");refresh();},onError:(e)=>setError(errorMessage(e))});
  const run=(fn:()=>Promise<unknown>)=>{setError("");action.mutate(fn);};
  const editTable=(r:OutletTable)=>{setTable(r);setTableName(r.name);setSeats(String(r.seats));};
  const newOrder=`/pos?location=${location}&outlet=${department}`;
  return <div className="space-y-3">
    <PageHeader title="Hotel POS · Food & Beverage" actions={<><Button variant="outline" size="sm" onClick={()=>window.print()}><Printer size={15}/>Print</Button></>}/>
    <div className="grid gap-2 sm:grid-cols-2 print:hidden">
      <SearchableSelect label="Hotel location" value={selection.location?.id} options={locations} onChange={v=>{setLocation(v);setDepartment(undefined);setParams(v?{location:String(v)}:{},{replace:true});setMode(undefined);setClosing(null);setTable(null);setTableName("");setOpening("");setCounted("");setReason("");setCashier("");setError("");}}/>
      <SearchableSelect label="Outlet" value={selection.department?.id} options={departments.map((r:any)=>({...r,name:r.code?`${r.code} · ${r.name}`:r.name}))} onChange={v=>{setDepartment(v);setParams({...selection.location?{location:String(selection.location.id)}:{},...v?{outlet:String(v)}:{}},{replace:true});setMode(undefined);setClosing(null);setTable(null);setTableName("");setOpening("");setCounted("");setReason("");setCashier("");setError("");}}/>
    </div>
    {selection.location&&<OutletSetup key={selection.location.id} userId={user?.id} locationId={selection.location.id} canManage={admin} onSaved={id=>{setDepartment(id);setParams({location:String(selection.location!.id),...id?{outlet:String(id)}:{}},{replace:true});setMode(undefined);setClosing(null);setTable(null);setError("");}}/>}
    <div className="hidden print:block text-sm">{locations.find((r:any)=>r.id===location)?.name} · {departments.find((r:any)=>r.id===department)?.name}</div>
    {options.isError&&<p role="alert" className="text-sm text-red-700">Hotel locations could not load. <button type="button" className="underline" onClick={()=>void options.refetch()}>Retry</button></p>}
    {selection.invalidLink&&<p role="status" className="text-sm text-slate-600">This link does not identify an accessible Hotel outlet. Choose an accessible Hotel location and outlet.</p>}
    {selection.valid?<>
      <nav className="flex gap-1 border-b print:hidden">{["Orders","Tables","Shifts","Reports","Setup"].filter(t=>t!=="Setup"||manage).map(t=><button key={t} className={`px-3 py-2 text-sm ${tab===t?"border-b-2 border-emerald-700 font-semibold text-emerald-800":"text-slate-600"}`} onClick={()=>setTab(t)}>{t}</button>)}</nav>
      {(context.isError||report.isError)&&<p role="alert" className="text-sm text-red-700">Outlet data could not load. {errorMessage(context.isError?context.error:report.error)}</p>}
      {error&&<p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {context.isLoading?<p>Loading outlet…</p>:context.isError?null:context.data&&!context.data.order_mode?<p className="text-sm">Configure TABLE, COUNTER or EVENT in Setup before opening a cashier shift.</p>:context.data?<p className="text-xs text-slate-500 print:hidden">{context.data.order_mode} orders · tables and shifts belong to this outlet</p>:null}
      {tab==="Setup"&&manage&&<div className="flex items-end gap-2 print:hidden"><label className="text-xs">Order mode<select aria-label="Outlet order mode" className={`block ${input}`} value={mode??context.data?.order_mode??"TABLE"} onChange={e=>setMode(e.target.value as OrderMode)}><option value="TABLE">Restaurant · table required</option><option value="COUNTER">Café · counter / optional table</option><option value="EVENT">Banquet · event, no table</option></select></label><Button disabled={action.isPending} onClick={()=>run(()=>operationsApi.policy(scope,mode??context.data?.order_mode??"TABLE"))}>Save mode</Button></div>}
      {tab==="Orders"&&<><div className="flex justify-end print:hidden">{sell&&context.data?.order_mode&&<Link className="rounded bg-emerald-700 px-3 py-2 text-sm text-white" to={newOrder}>Open order</Link>}</div><table className="w-full text-left text-sm"><thead><tr><th>Order</th><th>Table / event</th><th>Cashier</th><th className="text-right">Total</th><th/></tr></thead><tbody>{(context.data?.orders??[]).map(r=><tr key={r.id} className="border-t"><td className="py-2">{r.number}</td><td>{r.table||r.event||"Counter"}</td><td>{r.cashier_id}</td><td className="text-right">{money(r.total)}</td><td className="text-right">{sell&&r.cashier_id===user?.id&&<Link className="text-emerald-700 underline" to={`/pos?order=${r.id}`}>Continue / settle</Link>}</td></tr>)}</tbody></table>{context.data?.orders.length===0&&<p className="py-4 text-sm text-slate-500">No open orders in this outlet.</p>}</>}
      {tab==="Tables"&&<><div className="grid gap-2 md:grid-cols-4">{(context.data?.tables??[]).map(r=><div key={r.id} className="rounded border bg-white p-3"><strong>{r.name}</strong><div className="text-xs">{r.seats} seats · {!r.is_active?"INACTIVE":r.status}</div>{r.order_id&&<Link className="text-xs text-emerald-700 underline" to={`/pos?order=${r.order_id}`}>Continue order</Link>}{manage&&<div className="mt-2 flex gap-2 print:hidden"><button disabled={r.status==="OCCUPIED"} onClick={()=>editTable(r)} className="text-xs underline disabled:opacity-40">Edit</button><button disabled={r.status==="OCCUPIED"||action.isPending} onClick={()=>run(()=>operationsApi.table(scope,{name:r.name,seats:r.seats,is_active:!r.is_active},r.id))} className="text-xs underline disabled:opacity-40">{r.is_active?"Deactivate":"Activate"}</button></div>}</div>)}</div>{manage&&<div className="mt-3 flex flex-wrap gap-2 print:hidden"><input aria-label="Table name" className={input} placeholder="Table name" maxLength={30} value={tableName} onChange={e=>setTableName(e.target.value)}/><input aria-label="Table seats" className={`${input} w-20`} type="number" min={1} value={seats} onChange={e=>setSeats(e.target.value)}/><Button disabled={!tableName.trim()||Number(seats)<1||action.isPending} onClick={()=>run(()=>operationsApi.table(scope,{name:tableName.trim(),seats:Number(seats),is_active:table?.is_active??true},table?.id))}>{table?"Save table":"Create table"}</Button>{table&&<Button variant="ghost" onClick={()=>{setTable(null);setTableName("");}}>Cancel</Button>}</div>}</>}
      {tab==="Shifts"&&<><div className="flex gap-2 print:hidden">{sell&&!context.data?.shifts.some(s=>s.cashier_id===user?.id&&s.status==="OPEN")&&<><input aria-label="Opening cash" className={input} placeholder="Opening cash" type="number" min={0} step="0.01" value={opening} onChange={e=>setOpening(e.target.value)}/><Button disabled={!context.data?.order_mode||opening===""||Number(opening)<0||action.isPending} onClick={()=>run(()=>operationsApi.openShift(scope,opening))}>Open my shift</Button></>}</div>
        {(context.data?.shifts??[]).map(s=><section key={s.id} className="mt-3 rounded border bg-white p-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><strong>Shift #{s.id} · {s.cashier_name} · {s.status}</strong><span>{s.opened_at} {s.closed_at?`→ ${s.closed_at}`:""}</span></div><div className="mt-2 grid grid-cols-2 gap-2 lg:grid-cols-4"><span>Opening {money(s.opening_cash)}</span><span>Cash sales {money(s.payments.CASH)}</span><span>Expected {money(s.expected_cash)}</span><span>Counted {s.counted_cash===null?"—":money(s.counted_cash)}</span><span>Card {money(s.payments.CARD)}</span><span>Bank {money(s.payments.BANK_TRANSFER)}</span><span>PBJT {money(s.pbjt)}</span><span>Service {money(s.service_charge)}</span><span>Difference {s.cash_difference===null?"—":money(s.cash_difference)}</span><span>Open orders {s.open_orders}</span></div>{sell&&s.status==="OPEN"&&(s.cashier_id===user?.id||manage)&&<Button className="mt-2 print:hidden" size="sm" variant="outline" disabled={s.open_orders>0} onClick={()=>{setClosing(s);setCounted("");setReason("");}}>Close shift</Button>}
          <Link className="mt-2 inline-block text-xs text-emerald-700 underline print:hidden" target="_blank" to={`/pos/operations/shifts/${s.id}/print`}>Print shift report</Link>
          {s.transactions.length>0&&<details className="mt-2"><summary>Shift transactions</summary>{s.transactions.map(t=><div key={t.id} className="flex justify-between border-t py-1"><span>{t.number} · {t.method}</span><span>{money(t.total)}</span></div>)}</details>}
        </section>)}
        {closing&&<section className="mt-3 space-y-2 rounded border border-emerald-300 bg-white p-3 print:hidden"><strong>Close shift #{closing.id}</strong><div>Expected cash {money(closing.expected_cash)}</div><input aria-label="Counted cash" className={input} type="number" min={0} step="0.01" placeholder="Counted cash" value={counted} onChange={e=>setCounted(e.target.value)}/><input aria-label="Cash difference reason" className={`${input} w-full`} placeholder="Reason for any difference" value={reason} maxLength={1000} onChange={e=>setReason(e.target.value)}/><div className="flex gap-2"><Button disabled={counted===""||Number(counted)<0||action.isPending} onClick={()=>run(()=>operationsApi.closeShift(closing.id,counted,reason))}>Confirm close</Button><Button variant="ghost" onClick={()=>setClosing(null)}>Cancel</Button></div></section>}
      </>}
      {tab==="Reports"&&<><div className="flex flex-wrap gap-2 print:hidden"><input aria-label="From date" type="date" className={input} value={from} onChange={e=>setFrom(e.target.value)}/><input aria-label="To date" type="date" className={input} value={to} onChange={e=>setTo(e.target.value)}/><select aria-label="Report cashier" className={input} value={cashier} onChange={e=>setCashier(e.target.value)}><option value="">All cashiers</option>{[...new Set((context.data?.shifts??[]).map(s=>s.cashier_id))].map(id=><option key={id} value={id}>Cashier {id}</option>)}</select></div>{to<from&&<p className="text-red-700">Choose a valid date range.</p>}<h2 className="my-2 font-semibold">Outlet sales · {from} to {to}</h2>{report.data&&<><div className="grid grid-cols-2 gap-2 md:grid-cols-4">{[["Sales",report.data.sales],["Gross",money(report.data.gross)],["Cash",money(report.data.payments.CASH)],["Card",money(report.data.payments.CARD)],["Bank",money(report.data.payments.BANK_TRANSFER)],["Service charge",money(report.data.service_charge)],["PBJT",money(report.data.pbjt)],["Other tax",money(report.data.other_tax)]].map(([label,value])=><div key={label} className="rounded border bg-white p-2 text-sm"><div className="text-xs text-slate-500">{label}</div><strong>{value}</strong></div>)}</div><table className="mt-3 w-full text-left text-sm"><thead><tr><th>Date</th><th>Sales</th><th>Cash</th><th>Card</th><th>Bank</th><th>PBJT</th><th>Service</th><th>Total</th></tr></thead><tbody>{report.data.daily.map((d:any)=><tr key={d.date} className="border-t"><td className="py-2">{d.date}</td><td>{d.sales}</td><td>{money(d.payments.CASH)}</td><td>{money(d.payments.CARD)}</td><td>{money(d.payments.BANK_TRANSFER)}</td><td>{money(d.pbjt)}</td><td>{money(d.service_charge)}</td><td>{money(d.gross)}</td></tr>)}</tbody></table><h3 className="mt-3 font-semibold">Sales by cashier</h3>{report.data.cashiers.map((c:any)=><div key={c.cashier_id} className="flex justify-between border-t py-1 text-sm"><span>{c.name} · {c.sales} sales</span><span>{money(c.gross)}</span></div>)}</>}</>}
    </>:options.isLoading?<p className="text-sm text-slate-500">Loading Hotel locations…</p>:options.isError?null:locations.length===0?<p className="text-sm text-slate-500">No Hotel locations are available for this account. <Link className="text-emerald-700 underline" to="/pos">Open the Register for Catering sales</Link></p>:selection.location&&departments.length===0?<p className="text-sm text-slate-500">No Food &amp; Beverage outlets are configured for this Hotel location. {admin?"Use Manage F&B outlets above to create a Restaurant, Coffee Shop or another outlet.":"Ask an administrator to configure its F&B outlets."}</p>:<p className="text-sm text-slate-500">Choose a Hotel location and outlet.</p>}
  </div>;
}

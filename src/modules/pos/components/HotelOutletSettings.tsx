import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Button from "@/components/ui/Button";
import { operationsApi, type OrderMode, type OutletTable } from "../operationsApi";
const input="h-9 rounded border border-slate-300 bg-white px-2 text-sm";
export default function HotelOutletSettings({userId,locationId,departmentId}:{userId?:number;locationId:number;departmentId:number}) {
  const client=useQueryClient(),scope={location_id:locationId,department_id:departmentId};
  const context=useQuery({queryKey:["pos-operations",userId,locationId,departmentId],queryFn:async()=>(await operationsApi.context(scope)).data});
  const [mode,setMode]=useState<OrderMode>();
  const [table,setTable]=useState<OutletTable|null>(null),[name,setName]=useState(""),[seats,setSeats]=useState("2");
  const [error,setError]=useState("");
  const action=useMutation({mutationFn:async(fn:()=>Promise<unknown>)=>fn(),onSuccess:()=>{setError("");setTable(null);setName("");void client.invalidateQueries({queryKey:["pos-operations"]});void client.invalidateQueries({queryKey:["pos-outlet-setup"]});},onError:(e:unknown)=>{const err=e as {response?:{data?:{detail?:string}}};setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Could not save outlet settings');}});
  const edit=(row:OutletTable)=>{setTable(row);setName(row.name);setSeats(String(row.seats));};
  if(context.isLoading)return <p>Loading outlet settings…</p>;
  if(context.isError)return <p role="alert">Outlet settings could not load. <button type="button" className="underline" onClick={()=>void context.refetch()}>Retry</button></p>;
  return <section className="space-y-4 rounded-lg border bg-white p-4">
    <h2 className="font-semibold">Outlet orders and tables</h2>
    <div className="flex flex-wrap items-end gap-2"><label className="text-xs">Order mode<select aria-label="Outlet order mode" className={`block ${input}`} value={mode??context.data?.order_mode??""} disabled={action.isPending} onChange={e=>setMode(e.target.value as OrderMode)}><option value="" disabled>Choose mode</option><option value="TABLE">Restaurant · table required</option><option value="COUNTER">Café · counter / optional table</option><option value="EVENT">Banquet · event, no table</option></select></label><Button disabled={action.isPending||!(mode??context.data?.order_mode)} onClick={()=>action.mutate(()=>operationsApi.policy(scope,(mode??context.data!.order_mode)!))}>Save mode</Button></div>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Table</th><th>Seats</th><th>Status</th><th className="text-right">Actions</th></tr></thead><tbody>{(context.data?.tables??[]).map(row=><tr key={row.id} className="border-t"><td className="py-2">{row.name}</td><td>{row.seats}</td><td>{row.is_active?row.status:'INACTIVE'}</td><td className="space-x-3 text-right"><button type="button" className="text-emerald-700 underline disabled:opacity-40" disabled={row.status==='OCCUPIED'||action.isPending} onClick={()=>edit(row)}>Edit</button><button type="button" className="text-emerald-700 underline disabled:opacity-40" disabled={row.status==='OCCUPIED'||action.isPending} onClick={()=>action.mutate(()=>operationsApi.table(scope,{name:row.name,seats:row.seats,is_active:!row.is_active},row.id))}>{row.is_active?'Deactivate':'Activate'}</button></td></tr>)}</tbody></table></div>
    <fieldset disabled={action.isPending} className="flex flex-wrap items-end gap-2"><label className="text-xs">Table name<input aria-label="Table name" className={`block ${input}`} maxLength={30} value={name} onChange={e=>setName(e.target.value)}/></label><label className="text-xs">Seats<input aria-label="Table seats" className={`block ${input} w-20`} type="number" min={1} max={1000} value={seats} onChange={e=>setSeats(e.target.value)}/></label><Button disabled={!name.trim()||!Number.isInteger(Number(seats))||Number(seats)<1||Number(seats)>1000||action.isPending} onClick={()=>action.mutate(()=>operationsApi.table(scope,{name:name.trim(),seats:Number(seats),is_active:table?.is_active??true},table?.id))}>{table?'Save table':'Create table'}</Button>{table&&<Button variant="ghost" onClick={()=>{setTable(null);setName("");}}>Cancel</Button>}</fieldset>
    {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
  </section>;
}

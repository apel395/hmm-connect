import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Printer } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { listCategories, listFiscalGroups, saveCategory } from "./api";

const input = "h-8 w-full rounded border px-2 text-sm";
const empty = { code:"", name:"", fiscal_group_code:null, is_depreciable:true, default_useful_life_months:48,
  default_residual_percentage:0, asset_account_id:null, accumulated_depreciation_account_id:null,
  depreciation_expense_account_id:null, disposal_gain_account_id:null, disposal_loss_account_id:null,
  is_active:true, description:"" };
export default function AssetCategoryPage() {
  const qc=useQueryClient();
  const [form,setForm]=useState<any>(null);
  const [inactive,setInactive]=useState(false);
  const q=useQuery({queryKey:["asset-categories"],queryFn:listCategories});
  const groups=useQuery({queryKey:["asset-fiscal-groups"],queryFn:listFiscalGroups});
  const selected=groups.data?.find((g:any)=>g.code===form?.fiscal_group_code);
  const save=useMutation({mutationFn:()=>saveCategory(form),onSuccess:()=>{setForm(null);qc.invalidateQueries({queryKey:["asset-categories"]});toast.success("Category saved");},
    onError:(e:any)=>toast.error(typeof e?.response?.data?.detail==="string"?e.response.data.detail:"Check category fields")});
  return <div className="space-y-2">
    <PageHeader title="Asset Categories" actions={<><Button onClick={()=>setForm({...empty})}><Plus size={15}/>Category</Button><Button variant="outline" title="Print" aria-label="Print categories" onClick={()=>window.print()}><Printer size={15}/></Button></>}/>
    <div className="flex justify-end print:hidden"><label className="flex gap-2 text-xs"><input type="checkbox" checked={inactive} onChange={e=>setInactive(e.target.checked)}/>Show inactive categories</label></div>
    {form&&<Card className="grid gap-3 p-3 md:grid-cols-3">
      <label className="text-sm">Code<input className={input} maxLength={30} value={form.code} onChange={e=>setForm({...form,code:e.target.value})}/></label>
      <label className="text-sm">Category name<input className={input} maxLength={120} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
      <label className="text-sm">PPh group<select className={input} value={form.fiscal_group_code??""} onChange={e=>{const g=groups.data?.find((x:any)=>x.code===e.target.value);if(g)setForm({...form,fiscal_group_code:g.code,name:!form.name||groups.data?.some((x:any)=>x.name===form.name)?g.name:form.name,is_depreciable:g.code!=="LAND",default_useful_life_months:g.months,asset_account_id:null,accumulated_depreciation_account_id:null,depreciation_expense_account_id:null});}}><option value="">{form.id&&!form.fiscal_group_code?"Existing book category":"Choose group"}</option>{groups.data?.map((g:any)=><option key={g.code} value={g.code}>{g.name}</option>)}</select></label>
      <div className="text-sm">Fiscal useful life<br/><b>{selected?.months?`${selected.months/12} years`:selected?"Non-depreciable":"—"}</b></div>
      <div className="text-sm">Straight-line rate<br/><b>{selected?.straight_line_rate?`${selected.straight_line_rate}% / year`:"—"}</b></div>
      <div className="text-sm">Declining-balance rate<br/><b>{selected?.declining_balance_rate?`${selected.declining_balance_rate}% / year`:"—"}</b></div>
      <label className="text-sm md:col-span-3">Description<textarea rows={2} className="w-full rounded border p-2" value={form.description??""} onChange={e=>setForm({...form,description:e.target.value})}/></label>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})}/>Active</label>
      <div className="flex justify-end gap-2 md:col-span-2"><Button variant="outline" onClick={()=>setForm(null)}>Cancel</Button><Button disabled={save.isPending||!form.code.trim()||!form.name.trim()||(!form.id&&!form.fiscal_group_code)} onClick={()=>save.mutate()}>Save category</Button></div>
    </Card>}
    {q.isError&&<p role="alert">Could not load categories.</p>}
    <Table variant="grid" stickyHeader><THead><TR><TH>Code</TH><TH>Category</TH><TH>Fiscal useful life</TH><TH>Straight line / year</TH><TH>Declining balance / year</TH><TH>Description</TH><TH>Created by</TH><TH>Status</TH><TH>Actions</TH></TR></THead><TBody>
      {q.data?.filter((c:any)=>inactive||c.is_active).map((c:any)=><TR key={c.id}><TD>{c.code}</TD><TD>{c.name}{!c.fiscal_group_code&&<span className="ml-2 text-xs text-slate-500">Existing book category</span>}</TD><TD>{c.fiscal_group_code?(c.default_useful_life_months?`${c.default_useful_life_months/12} years`:"Non-depreciable"):(c.default_useful_life_months?`${c.default_useful_life_months} months`:"—")}</TD><TD>{c.straight_line_rate?`${c.straight_line_rate}%`:"—"}</TD><TD>{c.declining_balance_rate?`${c.declining_balance_rate}%`:"—"}</TD><TD title={c.description??""}>{c.description||"—"}</TD><TD>{c.creator||(c.source==="MMH_SETUP_SCRIPT"?"MMH setup script":"Unconfirmed")}</TD><TD>{c.is_active?"Active":"Inactive"}</TD><TD><Button size="xs" variant="outline" onClick={()=>setForm({...empty,...c})}>Edit</Button></TD></TR>)}
    </TBody></Table>
  </div>;
}

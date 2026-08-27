import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { filterBusinessUnits, listLocations } from "@/modules/admin/organization/api";
import { listBankAccounts, saveBankAccount } from "@/modules/finance/cash-flow/bankAccountApi";

const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const empty = { bank_name:"",account_name:"",account_number:"",account_holder:"",currency:"IDR",business_unit_id:0,location_id:null as number|null,coa_account_id:0,is_active:true };

export default function BankAccountFormPage() {
  const { id } = useParams();
  const editingId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form, setForm] = useState<any>(empty);

  const accounts = useQuery({ queryKey:["bank-accounts"], queryFn:()=>listBankAccounts(false), enabled:Boolean(editingId) });
  const businessUnits = useQuery({ queryKey:["business-units","bank-account","active"], queryFn:()=>filterBusinessUnits({is_active:true}) });
  const locations = useQuery({ queryKey:["bank-account-locations",form.business_unit_id], queryFn:()=>listLocations({business_unit_id:form.business_unit_id,is_active:true}), enabled:Boolean(form.business_unit_id) });
  const coa = useQuery({ queryKey:["bank-coa"], queryFn:()=>getAccountLookup({account_type:"ASSET",is_posting:true,is_active:true}) });

  const existing = useMemo(() => accounts.data?.find((row) => row.id === editingId), [accounts.data, editingId]);

  useEffect(() => {
    if (existing) setForm({ ...existing, location_id: existing.location_id ?? null });
  }, [existing]);

  useEffect(() => {
    if (!editingId && !form.business_unit_id && businessUnits.data?.length === 1) {
      setForm((current:any)=>({...current,business_unit_id:businessUnits.data![0].id}));
    }
  }, [editingId, form.business_unit_id, businessUnits.data]);

  const save = useMutation({
    mutationFn:()=>saveBankAccount({ ...form, id: editingId }),
    onSuccess:async()=>{
      await qc.invalidateQueries({queryKey:["bank-accounts"]});
      toast.success(editingId ? "Bank account updated" : "Bank account created");
      navigate("/finance-setup/bank-accounts");
    },
    onError:(error:any)=>toast.error(error.response?.data?.detail || "Bank account could not be saved"),
  });

  const valid = Boolean(form.bank_name?.trim() && form.account_name?.trim() && form.account_number?.trim() && form.business_unit_id && form.coa_account_id);

  return (
    <div className="space-y-5">
      <PageHeader title={editingId ? "Edit Bank Account" : "Create Bank Account"} description="Link a real funding account to one posting COA. Use Global / all locations for a corporate account shared by locations in the Business Unit." />
      <Card className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm">Bank Name *<input className={input} value={form.bank_name} onChange={(e)=>setForm({...form,bank_name:e.target.value})}/></label>
          <label className="text-sm">Account Name *<input className={input} value={form.account_name} onChange={(e)=>setForm({...form,account_name:e.target.value})}/></label>
          <label className="text-sm">Account Number *<input className={input} value={form.account_number} onChange={(e)=>setForm({...form,account_number:e.target.value})}/></label>
          <label className="text-sm">Account Holder<input className={input} value={form.account_holder ?? ""} onChange={(e)=>setForm({...form,account_holder:e.target.value})}/></label>
          <label className="text-sm">Currency<input className={input} maxLength={3} value={form.currency} onChange={(e)=>setForm({...form,currency:e.target.value.toUpperCase()})}/></label>
          <label className="text-sm">Business Unit *<select className={input} value={form.business_unit_id || ""} onChange={(e)=>setForm({...form,business_unit_id:Number(e.target.value),location_id:null})}><option value="">Select Business Unit</option>{businessUnits.data?.map((row:any)=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
          <label className="text-sm">Location<select className={input} disabled={!form.business_unit_id} value={form.location_id ?? ""} onChange={(e)=>setForm({...form,location_id:Number(e.target.value)||null})}><option value="">Global / all locations</option>{locations.data?.map((row:any)=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
          <label className="text-sm">Linked COA *<select className={input} value={form.coa_account_id || ""} onChange={(e)=>setForm({...form,coa_account_id:Number(e.target.value)})}><option value="">Select bank/cash posting account</option>{coa.data?.map((row:any)=><option key={row.id} value={row.id}>{row.account_code} — {row.account_name}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(form.is_active)} onChange={(e)=>setForm({...form,is_active:e.target.checked})}/>Active</label>
        </div>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={()=>navigate("/finance-setup/bank-accounts")}>Cancel</Button><Button disabled={!valid} loading={save.isPending} onClick={()=>save.mutate()}>{editingId?"Update Bank Account":"Create Bank Account"}</Button></div>
      </Card>
    </div>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";

type Settings = { input_vat_account_id: number | null };

export default function PostingRulesPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey:["direct-coa-settings"],
    queryFn:async()=>(await api.get<Settings>("/accounting/direct-coa-settings")).data,
  });
  const accounts = useQuery({
    queryKey:["direct-coa-settings","asset-lookup"],
    queryFn:()=>getAccountLookup({account_type:"ASSET",is_active:true,is_posting:true}),
  });
  const [inputVatAccountId,setInputVatAccountId]=useState<number|null>(null);
  const selected = inputVatAccountId ?? settings.data?.input_vat_account_id ?? null;
  const save = useMutation({
    mutationFn:async()=> {
      if (!selected) throw new Error("Choose the Input VAT account");
      return (await api.put<Settings>("/accounting/direct-coa-settings",{input_vat_account_id:selected})).data;
    },
    onSuccess:async(data)=>{
      setInputVatAccountId(data.input_vat_account_id);
      await queryClient.invalidateQueries({queryKey:["direct-coa-settings"]});
      toast.success("Direct COA settings saved");
    },
    onError:(error:any)=>toast.error(error.response?.data?.detail || error.message || "Settings could not be saved"),
  });

  return <div className="space-y-6">
    <PageHeader title="Direct COA Setup" description="COA mappings are maintained on the master records that own each accounting decision." />
    <Card className="border-emerald-200 bg-emerald-50/40">
      <h2 className="font-semibold text-emerald-950">Posting Rule transaction resolution is disabled</h2>
      <p className="mt-2 text-sm text-emerald-900">New journals resolve accounts directly from Item, Supplier, Bank/Cash, and global tax mappings. Historical rules and posted journals remain available and unchanged during migration.</p>
    </Card>
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <h2 className="font-semibold">Global Tax Mapping</h2>
        <p className="mt-1 text-sm text-slate-500">Used only for PPN Masukan on supplier invoices. No account number is hardcoded.</p>
        <label className="mt-4 block text-sm font-medium">Input VAT COA
          <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={selected ?? ""} onChange={(event)=>setInputVatAccountId(event.target.value?Number(event.target.value):null)}>
            <option value="">Select Input VAT account</option>
            {accounts.data?.map((account)=><option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}
          </select>
        </label>
        <div className="mt-4 flex justify-end"><Button disabled={!selected} loading={save.isPending} onClick={()=>save.mutate()}>Save Tax Mapping</Button></div>
      </Card>
      <Card>
        <h2 className="font-semibold">Mapping Ownership</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <div><dt className="font-medium">Item Master</dt><dd className="text-slate-500">Inventory Asset, Consumption/Expense, and COGS/Issue COA.</dd></div>
          <div><dt className="font-medium">Supplier Master</dt><dd className="text-slate-500">Accounts Payable COA.</dd></div>
          <div><dt className="font-medium">Bank/Cash Setup</dt><dd className="text-slate-500">Funding COA for payment journal credits.</dd></div>
          <div><dt className="font-medium">Journal Lines</dt><dd className="text-slate-500">Immutable account snapshots for posted history.</dd></div>
        </dl>
      </Card>
    </div>
  </div>;
}

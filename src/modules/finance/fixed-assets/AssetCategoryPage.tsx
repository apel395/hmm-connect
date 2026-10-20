import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Printer } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import type { AccountLookup } from "@/modules/master/chart-of-accounts/types";
import { listCategories, saveCategory } from "./api";
import { assetType, fixedAssetAccount, accumulatedDepreciationAccount, depreciationExpenseAccount } from "./accountRules";

const input = "h-9 w-full rounded border px-2 text-sm";
const empty = {
  code: "",
  name: "",
  is_depreciable: true,
  default_useful_life_months: 48,
  default_residual_percentage: 0,
  asset_account_id: "",
  accumulated_depreciation_account_id: "",
  depreciation_expense_account_id: "",
  disposal_gain_account_id: null,
  disposal_loss_account_id: null,
  is_active: true,
  description: "",
};

export default function AssetCategoryPage() {
  const qc = useQueryClient();
  const [showForm,setShowForm] = useState(false);
  const [form, setForm] = useState<any>({ ...empty });
  const categories = useQuery({ queryKey: ["asset-categories"], queryFn: listCategories });
  const assetLookup = useQuery({
    queryKey: ["category-account-lookup", "ASSET"],
    queryFn: () => getAllAccountLookup({ account_type: "ASSET", is_active: true, is_posting: true }),
  });
  const expenseLookup = useQuery({
    queryKey: ["category-account-lookup", "EXPENSE"],
    queryFn: () => getAllAccountLookup({ account_type: "EXPENSE", is_active: true, is_posting: true }),
  });

  const revenueLookup = useQuery({queryKey:["category-account-lookup","REVENUE"],queryFn:()=>getAllAccountLookup({account_type:"REVENUE",is_active:true,is_posting:true})});
  const assetAccounts = (assetLookup.data ?? []).filter(fixedAssetAccount);
  const accumulatedAccounts = (assetLookup.data ?? []).filter(accumulatedDepreciationAccount);
  const expenseAccounts = (expenseLookup.data ?? []).filter(depreciationExpenseAccount);

  const save = useMutation({
    mutationFn: () => saveCategory({
      ...form,
      default_useful_life_months: form.is_depreciable ? Number(form.default_useful_life_months) : null,
      ...Object.fromEntries(
        ["asset_account_id", "accumulated_depreciation_account_id", "depreciation_expense_account_id",
          "disposal_gain_account_id", "disposal_loss_account_id"].map(key => [
          key, form[key] ? Number(form[key]) : null,
        ]),
      ),
    }),
    onSuccess: () => {
      setForm({ ...empty });
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["asset-categories"] });
      toast.success("Asset category saved.");
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Could not save category."),
  });

  const accountField = (key: string, label: string, options: AccountLookup[]) => (
    <label className="space-y-1 text-sm" key={key}>
      <span className="font-medium">{label}</span>
      <select
        className={input}
        value={form[key] ?? ""}
        onChange={event => { const land = key === "asset_account_id" && options.find(a=>a.id===Number(event.target.value))?.account_code === "100-600-100"; setForm({ ...form, [key]: event.target.value, ...(land ? { is_depreciable:false, default_useful_life_months:"", accumulated_depreciation_account_id:"", depreciation_expense_account_id:"" } : {}) }); }}
      >
        <option value="">Select {label.toLowerCase()}</option>
        {options.map(account => (
          <option key={account.id} value={account.id}>
            {account.account_code} — {account.account_name}
          </option>
        ))}
      </select>
    </label>
  );

  const ready = Boolean(form.code.trim() && form.name.trim() && form.asset_account_id && (!form.is_depreciable || (Number(form.default_useful_life_months) >= 48 && form.accumulated_depreciation_account_id && form.depreciation_expense_account_id)));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Asset Categories"
        description="Default useful life and COA mappings."
        actions={<><Button onClick={()=>setShowForm(!showForm)}><Plus size={16}/> Category</Button><Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button></>}
      />
      {showForm && <Card className="grid gap-3 p-4 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Code</span>
          <input className={input} value={form.code} onChange={event => setForm({ ...form, code: event.target.value })} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Category name</span>
          <input className={input} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_depreciable} onChange={e=>setForm({...form,is_depreciable:e.target.checked,...(!e.target.checked?{default_useful_life_months:"",accumulated_depreciation_account_id:"",depreciation_expense_account_id:""}:{default_useful_life_months:48})})}/>Depreciable</label>
        {form.is_depreciable && <label className="space-y-1 text-sm">
          <span className="font-medium">Useful life (months, minimum 48)</span>
          <input className={input} type="number" min={48} value={form.default_useful_life_months}
            onChange={event => setForm({ ...form, default_useful_life_months: Number(event.target.value) })} />
        </label>}
        {accountField("asset_account_id", "Fixed asset account", assetAccounts)}
        <div className="flex items-center text-xs text-slate-600">Asset type: {form.asset_account_id ? assetType(assetAccounts.find(a => a.id === Number(form.asset_account_id))?.account_code ?? "") : "Select an asset account"}</div>
        {form.is_depreciable && accountField("accumulated_depreciation_account_id", "Accumulated depreciation account", accumulatedAccounts)}
        {form.is_depreciable && accountField("depreciation_expense_account_id", "Depreciation expense account", expenseAccounts)}
        <label className="space-y-1 text-sm">
          <span className="font-medium">Residual value (%)</span>
          <input className={input} type="number" min={0} max={99.99} step={0.01}
            value={form.default_residual_percentage}
            onChange={event => setForm({ ...form, default_residual_percentage: Number(event.target.value) })} />
        </label>
        {accountField("disposal_gain_account_id","Disposal gain account",(revenueLookup.data??[]))}
        {accountField("disposal_loss_account_id","Disposal loss account",(expenseLookup.data??[]).filter(a=>a.normal_balance==="DEBIT"))}
        <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})}/>Active</label>
        <div className="flex items-end">
          <Button variant="outline" onClick={()=>setShowForm(false)}>Close</Button>
          <Button disabled={!ready || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving..." : form.id ? "Update Category" : "Save Category"}
          </Button>
        </div>
      </Card>}
      <Table variant="grid" stickyHeader containerClassName="max-h-[60vh] overflow-auto">
        <THead><TR><TH>Code</TH><TH>Name</TH><TH>Asset Type</TH><TH>Policy</TH><TH>Useful Life</TH><TH>Residual %</TH><TH>Status</TH><TH>Actions</TH></TR></THead>
        <TBody>
          {categories.data?.map((category: any) => (
            <TR key={category.id}>
              <TD>{category.code}</TD><TD>{category.name}</TD><TD>{assetType(assetAccounts.find(a => a.id === category.asset_account_id)?.account_code ?? "")}</TD>
              <TD>{category.is_depreciable ? "Straight Line" : "Non-depreciable"}</TD><TD>{category.is_depreciable ? `${category.default_useful_life_months} months` : "—"}</TD>
              <TD>{category.default_residual_percentage}</TD>
              <TD>{category.is_active ? "Active" : "Inactive"}</TD>
              <TD><Button size="xs" variant="outline" onClick={() => {setForm(category);setShowForm(true);}}>Edit</Button></TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

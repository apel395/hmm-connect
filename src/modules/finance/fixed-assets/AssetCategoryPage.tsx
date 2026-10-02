import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import type { AccountLookup } from "@/modules/master/chart-of-accounts/types";
import { listCategories, saveCategory } from "./api";

const input = "h-9 w-full rounded border px-2 text-sm";
const empty = {
  code: "",
  name: "",
  default_useful_life_months: "",
  default_residual_percentage: 0,
  asset_account_id: "",
  accumulated_depreciation_account_id: "",
  depreciation_expense_account_id: "",
  disposal_gain_account_id: null,
  disposal_loss_account_id: null,
  is_active: true,
  description: "",
};

const isFixedAsset = (account: AccountLookup) =>
  account.account_type === "ASSET" &&
  account.normal_balance === "DEBIT" &&
  account.account_code?.startsWith("100-600-");

const isAccumulatedDepreciation = (account: AccountLookup) =>
  account.account_type === "ASSET" &&
  account.normal_balance === "CREDIT" &&
  account.account_code?.startsWith("100-800-");

const isDepreciationExpense = (account: AccountLookup) =>
  account.account_type === "EXPENSE" &&
  account.normal_balance === "DEBIT" &&
  /penyusutan|depresiasi|depreciation/i.test(account.account_name);

export default function AssetCategoryPage() {
  const qc = useQueryClient();
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

  const assetAccounts = (assetLookup.data ?? []).filter(isFixedAsset);
  const accumulatedAccounts = (assetLookup.data ?? []).filter(isAccumulatedDepreciation);
  const expenseAccounts = (expenseLookup.data ?? []).filter(isDepreciationExpense);

  const save = useMutation({
    mutationFn: () => saveCategory({
      ...form,
      ...Object.fromEntries(
        ["asset_account_id", "accumulated_depreciation_account_id", "depreciation_expense_account_id",
          "disposal_gain_account_id", "disposal_loss_account_id"].map(key => [
          key, form[key] ? Number(form[key]) : null,
        ]),
      ),
    }),
    onSuccess: () => {
      setForm({ ...empty });
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
        onChange={event => setForm({ ...form, [key]: event.target.value })}
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

  const ready = Boolean(form.code.trim() && form.name.trim() && Number(form.default_useful_life_months) > 0 &&
    form.asset_account_id && form.accumulated_depreciation_account_id && form.depreciation_expense_account_id);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Asset Categories"
        description="Default useful life and COA mappings."
        actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>}
      />
      <Card className="grid gap-3 p-4 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Code</span>
          <input className={input} value={form.code} onChange={event => setForm({ ...form, code: event.target.value })} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Category name</span>
          <input className={input} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Useful life (months)</span>
          <input className={input} type="number" min={1} value={form.default_useful_life_months}
            onChange={event => setForm({ ...form, default_useful_life_months: Number(event.target.value) })} />
        </label>
        {accountField("asset_account_id", "Fixed asset account", assetAccounts)}
        {accountField("accumulated_depreciation_account_id", "Accumulated depreciation account", accumulatedAccounts)}
        {accountField("depreciation_expense_account_id", "Depreciation expense account", expenseAccounts)}
        <label className="space-y-1 text-sm">
          <span className="font-medium">Residual value (%)</span>
          <input className={input} type="number" min={0} max={99.99} step={0.01}
            value={form.default_residual_percentage}
            onChange={event => setForm({ ...form, default_residual_percentage: Number(event.target.value) })} />
        </label>
        <div className="flex items-end">
          <Button disabled={!ready || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving..." : form.id ? "Update Category" : "Save Category"}
          </Button>
        </div>
      </Card>
      <Table variant="grid">
        <THead><TR><TH>Code</TH><TH>Name</TH><TH>Useful Life</TH><TH>Residual %</TH><TH>Status</TH><TH>Actions</TH></TR></THead>
        <TBody>
          {categories.data?.map((category: any) => (
            <TR key={category.id}>
              <TD>{category.code}</TD><TD>{category.name}</TD>
              <TD>{category.default_useful_life_months} months</TD>
              <TD>{category.default_residual_percentage}</TD>
              <TD>{category.is_active ? "Active" : "Inactive"}</TD>
              <TD><Button size="xs" variant="outline" onClick={() => setForm(category)}>Edit</Button></TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

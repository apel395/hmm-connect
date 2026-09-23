import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import SearchableSelect from "@/components/form/SearchableSelect";
import type { InventoryTreatment, ItemType, Product, ProductGroup, TaxCategory } from "../types";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";

const UOMS = ["Kg", "Gram", "Liter", "Ml", "Bottle", "Box", "Pack", "Pcs", "Can", "Roll", "Meter", "Set"];
const TAX_CATEGORIES: { value: TaxCategory; label: string; help: string }[] = [
  { value: "REVIEW_REQUIRED", label: "Review Required", help: "Belum diklasifikasikan. Finance harus menetapkan perlakuan PPN sebelum dokumen dilanjutkan." },
  { value: "STANDARD", label: "Standard PPN", help: "Item kena PPN dengan tarif yang ditetapkan di Item Master." },
  { value: "EXEMPT", label: "PPN Dibebaskan", help: "Item mendapat fasilitas pembebasan PPN." },
  { value: "NON_VAT", label: "Non PPN", help: "Item bukan objek PPN untuk transaksi pembelian ini." },
  { value: "SPECIAL", label: "Perlakuan Khusus", help: "Gunakan tarif khusus dan isi alasan/referensi Finance." },
];

const TREATMENTS: { value: InventoryTreatment; label: string; help: string }[] = [
  { value: "REVIEW_REQUIRED", label: "Review Required", help: "Belum ditentukan apakah item disimpan, dipakai langsung, aset tetap, atau non-stock." },
  { value: "STOCK", label: "Stock / Warehouse", help: "Masuk persediaan gudang. Receiving mendebit Inventory Asset." },
  { value: "DIRECT_USE", label: "Direct Use", help: "Tidak masuk stok. Receiving langsung mendebit expense/consumption." },
  { value: "FIXED_ASSET", label: "Fixed Asset", help: "Dikapitalisasi ke akun aset tetap, bukan persediaan gudang." },
  { value: "NON_STOCK", label: "Non-stock / Service", help: "Jasa atau pembelian non-persediaan yang langsung dibebankan ke akun expense." },
];

interface Props {
  open: boolean;
  product?: Product | null;
  groups?: ProductGroup[];
  loading?: boolean;
  onClose: () => void;
  onSubmit: (payload: any) => void;
}

const blank = () => ({
  code: "", name: "", item_type: "BUY" as ItemType,
  group_code: "", group_name: "", subgroup_code: "", subgroup_name: "",
  uom: "", usage_uom: "", conversion: 1, minimum_stock: 0, cost_price: 0, selling_price: 0,
  inventory_treatment: "REVIEW_REQUIRED" as InventoryTreatment,
  tax_category: "REVIEW_REQUIRED" as TaxCategory,
  is_taxable: false,
  tax_rate: 0,
  tax_reason: "",
  tax_reference: "",
  inventory_account_id: null as number | null,
  purchase_account_id: null as number | null,
  cogs_account_id: null as number | null,
  asset_account_id: null as number | null,
});

export default function ProductForm({ open, product, groups = [], loading, onClose, onSubmit }: Props) {
  const [form, setForm] = useState(blank());
  const accounts = useQuery({
    queryKey: ["product-coa-lookup", "all-active-posting"],
    queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }),
  });

  const groupOptions = useMemo(() => {
    const visible = groups.filter((group) => group.item_type === form.item_type);
    const set = new Map<string, { code: string; name: string }>();
    visible.forEach((item) => set.set(item.code, { code: item.code, name: item.name }));
    if (product?.group_code && product.group_name) set.set(product.group_code, { code: product.group_code, name: product.group_name });
    return [...set.values()]
      .sort((a, b) => a.code.localeCompare(b.code))
      .map((item) => ({ id: item.code, label: `${item.code} — ${item.name}`, keywords: [item.code, item.name] }));
  }, [groups, form.item_type, product]);

  const subGroupOptions = useMemo(() => {
    const selected = groups.find((group) => group.code === form.group_code);
    const set = new Map<string, { code: string; name: string }>();
    (selected?.subgroups ?? []).forEach((sub) => {
      if (sub.code && sub.name) set.set(sub.code, { code: sub.code, name: sub.name === "GRESORIS" ? "GROCERIES" : sub.name });
    });
    if (product && product.group_code === form.group_code && product.subgroup_code && product.subgroup_name) {
      set.set(product.subgroup_code, { code: product.subgroup_code, name: product.subgroup_name === "GRESORIS" ? "GROCERIES" : product.subgroup_name });
    }
    return [...set.values()]
      .sort((a, b) => a.code.localeCompare(b.code))
      .map((item) => ({ id: item.code, label: `${item.code} — ${item.name}`, keywords: [item.code, item.name] }));
  }, [groups, form.group_code, product]);

  const allAccounts = accounts.data ?? [];
  const inventoryAccounts = allAccounts.filter((account) =>
    account.account_type === "ASSET" &&
    account.normal_balance === "DEBIT" &&
    account.account_code.startsWith("100-300-")
  );
  const fixedAssetAccounts = allAccounts.filter((account) =>
    account.account_type === "ASSET" &&
    account.normal_balance === "DEBIT" &&
    ["100-600-", "100-700-", "100-900-"].some((prefix) => account.account_code.startsWith(prefix))
  );
  const expenseAccounts = allAccounts.filter((account) =>
    account.account_type === "EXPENSE" && account.normal_balance === "DEBIT"
  );

  const coaOptions = (rows: typeof allAccounts) => rows.map((account) => ({
    id: account.id,
    label: `${account.account_code} — ${account.account_name}`,
    keywords: [account.account_code, account.account_name],
  }));

  useEffect(() => {
    if (!open) return;
    setForm(product ? {
      code: product.code,
      name: product.name,
      item_type: product.item_type ?? "BUY",
      group_code: product.group_code,
      group_name: product.group_name,
      subgroup_code: product.subgroup_code,
      subgroup_name: product.subgroup_name === "GRESORIS" ? "GROCERIES" : product.subgroup_name,
      uom: product.uom,
      usage_uom: product.usage_uom,
      conversion: Number(product.conversion),
      minimum_stock: Number(product.minimum_stock ?? 0),
      cost_price: Number(product.cost_price ?? 0),
      selling_price: Number(product.selling_price ?? 0),
      inventory_treatment: product.inventory_treatment ?? "REVIEW_REQUIRED",
      tax_category: product.tax_category ?? "REVIEW_REQUIRED",
      is_taxable: Boolean(product.is_taxable),
      tax_rate: Number(product.tax_rate ?? 0),
      tax_reason: product.tax_reason ?? "",
      tax_reference: product.tax_reference ?? "",
      inventory_account_id: product.inventory_account_id ?? null,
      purchase_account_id: product.purchase_account_id ?? null,
      cogs_account_id: product.cogs_account_id ?? null,
      asset_account_id: product.asset_account_id ?? null,
    } : blank());
  }, [open, product]);

  const update = (key: string, value: unknown) => setForm((current) => ({ ...current, [key]: value }));

  const changeItemType = (value: ItemType) => {
    setForm((current) => ({
      ...current,
      item_type: value,
      group_code: "",
      group_name: "",
      subgroup_code: "",
      subgroup_name: "",
    }));
  };

  const changeTreatment = (value: InventoryTreatment) => {
    setForm((current) => ({
      ...current,
      inventory_treatment: value,
      inventory_account_id: value === "STOCK" ? current.inventory_account_id : null,
      purchase_account_id: ["DIRECT_USE", "NON_STOCK"].includes(value) ? current.purchase_account_id : null,
      asset_account_id: value === "FIXED_ASSET" ? current.asset_account_id : null,
    }));
  };

  const changeTaxCategory = (value: TaxCategory) => {
    const taxable = value === "STANDARD" || value === "SPECIAL";
    setForm((current) => ({
      ...current,
      tax_category: value,
      is_taxable: taxable,
      tax_rate: taxable ? current.tax_rate : 0,
    }));
  };

  const updateGroup = (value: string | undefined) => {
    const code = value ?? "";
    const group = groups.find((item) => item.code === code);
    setForm((current) => ({
      ...current,
      group_code: code,
      group_name: group?.name ?? "",
      subgroup_code: "",
      subgroup_name: "",
    }));
  };

  const updateSubgroup = (value: string | undefined) => {
    const code = value ?? "";
    const group = groups.find((item) => item.code === form.group_code);
    const sub = (group?.subgroups ?? []).find((item) => item.code === code);
    const name = sub?.name === "GRESORIS" ? "GROCERIES" : sub?.name;
    setForm((current) => ({ ...current, subgroup_code: code, subgroup_name: name ?? "" }));
  };

  const accountingReady =
    form.inventory_treatment === "REVIEW_REQUIRED" ||
    (form.inventory_treatment === "STOCK" && Boolean(form.inventory_account_id)) ||
    (["DIRECT_USE", "NON_STOCK"].includes(form.inventory_treatment) && Boolean(form.purchase_account_id)) ||
    (form.inventory_treatment === "FIXED_ASSET" && Boolean(form.asset_account_id));

  const taxReady =
    form.tax_category === "REVIEW_REQUIRED" ||
    (["EXEMPT", "NON_VAT"].includes(form.tax_category)) ||
    (form.is_taxable && Number(form.tax_rate) > 0);

  const subgroupRequired = form.item_type === "BUY";
  const valid = Boolean(
    form.code.trim() &&
    form.name.trim() &&
    form.group_code &&
    (!subgroupRequired || form.subgroup_code) &&
    form.uom.trim() &&
    form.usage_uom.trim() &&
    Number(form.conversion) > 0 &&
    Number(form.minimum_stock) >= 0 &&
    accountingReady &&
    taxReady
  );

  const submit = () => {
    const payload = {
      ...form,
      code: form.code.trim(),
      name: form.name.trim(),
      subgroup_name: form.subgroup_name === "GRESORIS" ? "GROCERIES" : form.subgroup_name,
      uom: form.uom.trim(),
      usage_uom: form.usage_uom.trim(),
      conversion: Number(form.conversion),
      minimum_stock: Number(form.minimum_stock),
      cost_price: Number(form.cost_price),
      selling_price: Number(form.selling_price),
      tax_rate: Number(form.tax_rate),
      tax_reason: form.tax_reason || null,
      tax_reference: form.tax_reference || null,
    };
    if (product) {
      const { code: _unchangedCode, ...rest } = payload;
      onSubmit(rest);
      return;
    }
    onSubmit(payload);
  };

  const selectedTax = TAX_CATEGORIES.find((item) => item.value === form.tax_category);
  const selectedTreatment = TREATMENTS.find((item) => item.value === form.inventory_treatment);

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-4xl">
      <DialogHeader><DialogTitle>{product ? "Edit Item" : "New Item"}</DialogTitle></DialogHeader>
      <DialogBody>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 font-semibold text-slate-900">Item Type</div>
            <div className="grid grid-cols-2 gap-2">
              {(["BUY", "SELL"] as ItemType[]).map((value) => (
                <button key={value} type="button" onClick={() => changeItemType(value)} className={`h-10 rounded-md border px-3 text-sm font-medium ${form.item_type === value ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 bg-white text-slate-600"}`}>
                  {value === "BUY" ? "Buy Item" : "Sell Item"}
                </button>
              ))}
            </div>
          </div>

          <label className="col-span-2 text-sm font-medium">Product Code
            <Input className="mt-1" disabled={Boolean(product)} maxLength={20} value={form.code} onChange={(event) => update("code", event.target.value)} />
          </label>
          <label className="col-span-2 text-sm font-medium">Product Name
            <Input className="mt-1" value={form.name} onChange={(event) => update("name", event.target.value)} />
          </label>

          <SearchableSelect label="Group" value={form.group_code || undefined} required placeholder="Type group code or name..." options={groupOptions} onChange={updateGroup} />
          <SearchableSelect label="Sub Group" value={form.subgroup_code || undefined} required={subgroupRequired} disabled={!form.group_code} placeholder={form.group_code ? "Type subgroup code or name..." : "Select Group first"} options={subGroupOptions} onChange={updateSubgroup} />

          <label className="text-sm font-medium">Purchase UOM
            <Input className="mt-1" list="purchase-uom-options" value={form.uom} onChange={(event) => update("uom", event.target.value)} />
            <datalist id="purchase-uom-options">{UOMS.map((uom) => <option key={uom} value={uom}/>)}</datalist>
          </label>
          <label className="text-sm font-medium">Usage UOM
            <Input className="mt-1" list="usage-uom-options" value={form.usage_uom} onChange={(event) => update("usage_uom", event.target.value)} />
            <datalist id="usage-uom-options">{UOMS.map((uom) => <option key={uom} value={uom}/>)}</datalist>
          </label>

          <label className="text-sm font-medium">Conversion
            <Input className="mt-1" type="number" min="0.0001" step="0.0001" value={form.conversion} onChange={(event) => update("conversion", Number(event.target.value))} />
          </label>
          <label className="text-sm font-medium">Minimum Stock
            <Input className="mt-1" type="number" min="0" step="0.01" value={form.minimum_stock} onChange={(event) => update("minimum_stock", Number(event.target.value))} />
          </label>

          <div className="col-span-2 rounded-lg border border-emerald-200 bg-emerald-50/30 p-4">
            <div className="mb-3">
              <div className="font-semibold text-slate-900">Inventory Treatment</div>
              <div className="text-xs text-slate-500">Controls whether receiving goes to warehouse stock, direct expense, fixed asset, or non-stock expense.</div>
            </div>
            <label className="text-sm font-medium">Treatment
              <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.inventory_treatment} onChange={(event) => changeTreatment(event.target.value as InventoryTreatment)}>
                {TREATMENTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
              <span className="mt-1 block text-xs font-normal text-slate-500">{selectedTreatment?.help}</span>
            </label>

            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              {form.inventory_treatment === "STOCK" && <SearchableSelect
                label="Inventory Asset COA"
                value={form.inventory_account_id ?? undefined}
                required
                placeholder="Type inventory COA..."
                options={coaOptions(inventoryAccounts)}
                onChange={(value) => update("inventory_account_id", value ? Number(value) : null)}
              />}
              {["DIRECT_USE", "NON_STOCK"].includes(form.inventory_treatment) && <SearchableSelect
                label="Expense / Consumption COA"
                value={form.purchase_account_id ?? undefined}
                required
                placeholder="Type expense COA..."
                options={coaOptions(expenseAccounts)}
                onChange={(value) => update("purchase_account_id", value ? Number(value) : null)}
              />}
              {form.inventory_treatment === "FIXED_ASSET" && <SearchableSelect
                label="Fixed Asset COA"
                value={form.asset_account_id ?? undefined}
                required
                placeholder="Type fixed asset COA..."
                options={coaOptions(fixedAssetAccounts)}
                onChange={(value) => update("asset_account_id", value ? Number(value) : null)}
              />}
              {form.inventory_treatment === "STOCK" && <SearchableSelect
                label="COGS / Issue COA"
                value={form.cogs_account_id ?? undefined}
                placeholder="Type COGS or issue expense COA..."
                options={coaOptions(expenseAccounts)}
                onChange={(value) => update("cogs_account_id", value ? Number(value) : null)}
              />}
            </div>
          </div>

          <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3">
              <div className="font-semibold text-slate-900">PPN / Tax Profile</div>
              <div className="text-xs text-slate-500">Tax profile is snapshotted into future purchasing documents. Do not infer tax from classification.</div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm font-medium">Tax Treatment
                <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.tax_category} onChange={(event) => changeTaxCategory(event.target.value as TaxCategory)}>
                  {TAX_CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
                <span className="mt-1 block text-xs font-normal text-slate-500">{selectedTax?.help}</span>
              </label>
              <label className="text-sm font-medium">PPN Rate (%)
                <Input className="mt-1" type="number" min="0" max="100" step="0.01" disabled={!form.is_taxable} value={form.is_taxable ? form.tax_rate : 0} onChange={(event) => update("tax_rate", Number(event.target.value))} />
              </label>
              <label className="col-span-2 text-sm font-medium">Tax Reason / Notes
                <Input className="mt-1" value={form.tax_reason} onChange={(event) => update("tax_reason", event.target.value)} />
              </label>
              <label className="col-span-2 text-sm font-medium">Tax Reference
                <Input className="mt-1" value={form.tax_reference} onChange={(event) => update("tax_reference", event.target.value)} />
              </label>
            </div>
          </div>
        </div>
      </DialogBody>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button disabled={!valid} loading={loading} onClick={submit}>Save</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}

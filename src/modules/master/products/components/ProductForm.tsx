import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import SearchableSelect from "@/components/form/SearchableSelect";
import type { ItemType, Product, ProductGroup, TaxCategory } from "../types";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";

const UOMS = ["Kg", "Gram", "Liter", "Ml", "Bottle", "Box", "Pack", "Pcs", "Can", "Roll", "Meter", "Set"];
const TAX_CATEGORIES: { value: TaxCategory; label: string; help: string }[] = [
  { value: "REVIEW_REQUIRED", label: "Review Required", help: "Belum diklasifikasikan. Finance harus menetapkan perlakuan PPN sebelum dokumen dilanjutkan." },
  { value: "STANDARD", label: "Standard PPN", help: "Item kena PPN dengan tarif default pada Item Master." },
  { value: "EXEMPT", label: "PPN Dibebaskan", help: "Item mendapat fasilitas pembebasan PPN." },
  { value: "NON_VAT", label: "Non PPN", help: "Item bukan objek PPN untuk penggunaan transaksi ini." },
  { value: "SPECIAL", label: "Perlakuan Khusus", help: "Gunakan untuk item dengan perlakuan pajak khusus dan isi alasan/referensi." },
];
const COA_FIELDS: [string, "inventory_account_id" | "purchase_account_id" | "cogs_account_id", string][] = [
  ["Inventory Asset COA", "inventory_account_id", "Dipakai saat item diterima/di-stock. Set hanya jika item disimpan sebagai persediaan."],
  ["Consumption / Expense COA", "purchase_account_id", "Dipakai untuk pembelian langsung (non-stock) dan Purchase Requisition."],
  ["COGS Asset COA", "cogs_account_id", "Dipakai saat stok gudang dikeluarkan/dikonsumsi (cost of goods sold)."],
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
  code:"", name:"", item_type:"BUY" as ItemType,
  group_code:"", group_name:"", subgroup_code:"", subgroup_name:"",
  uom:"", usage_uom:"", conversion:1, minimum_stock:0, cost_price:0, selling_price:0,
  tax_category:"REVIEW_REQUIRED" as TaxCategory,
  is_taxable:false,
  tax_rate:0,
  tax_reason:"",
  tax_reference:"",
  inventory_account_id:null as number|null,
  purchase_account_id:null as number|null,
  cogs_account_id:null as number|null,
});

export default function ProductForm({ open, product, groups = [], loading, onClose, onSubmit }: Props) {
  const [form, setForm] = useState(blank());
  const accounts = useQuery({queryKey:["product-coa-lookup"],queryFn:()=>getAccountLookup({is_active:true,is_posting:true,page:1,page_size:1000})});

  const groupOptions = useMemo(() => {
    const visible = groups.filter((group) => group.item_type === form.item_type);
    const selected = product && product.item_type === form.item_type && product.group_code && product.group_name
      ? {code:product.group_code, name:product.group_name}
      : null;
    const set = new Map<string, {code:string;name:string}>();
    [...visible, ...(selected ? [selected] : [])].forEach((item) => set.set(item.code, {code:item.code, name:item.name}));
    const list = [...set.values()];
    if (product && product.group_code === form.group_code && product.group_name) {
      const exists = list.some((item) => item.code === product.group_code);
      if (!exists) list.push({code:product.group_code, name:product.group_name});
    }
    return list.sort((a,b) => a.code.localeCompare(b.code)).map((item) => ({id:item.code, label:`${item.code} — ${item.name}`, keywords:[item.code,item.name]}));
  }, [groups, form.item_type, form.group_code, product]);

  const subGroupOptions = useMemo(() => {
    const selected = groups.find((group) => group.code === form.group_code);
    const set = new Map<string, {code:string;name:string}>();
    (selected?.subgroups ?? []).forEach((sub) => { if (sub.code && sub.name) set.set(sub.code, {code:sub.code, name:sub.name}); });
    if (product && product.group_code === form.group_code && product.subgroup_code && product.subgroup_name) {
      set.set(product.subgroup_code, {code:product.subgroup_code, name:product.subgroup_name});
    }
    return [...set.values()].sort((a,b) => a.code.localeCompare(b.code)).map((item) => ({id:item.code, label:`${item.code} — ${item.name}`, keywords:[item.code,item.name]}));
  }, [groups, form.group_code, product]);

  const subgroupRequired = form.item_type === "BUY";
  const selectedTax = TAX_CATEGORIES.find((item) => item.value === form.tax_category);

  useEffect(() => {
    if (!open) return;
    setForm(product ? {
      code:product.code, name:product.name, item_type:product.item_type ?? "BUY",
      group_code:product.group_code, group_name:product.group_name,
      subgroup_code:product.subgroup_code, subgroup_name:product.subgroup_name,
      uom:product.uom, usage_uom:product.usage_uom, conversion:Number(product.conversion),
      minimum_stock:Number(product.minimum_stock ?? 0),
      cost_price:Number(product.cost_price ?? 0),
      selling_price:Number(product.selling_price ?? 0),
      tax_category:product.tax_category ?? "REVIEW_REQUIRED",
      is_taxable:Boolean(product.is_taxable),
      tax_rate:Number(product.tax_rate ?? 0),
      tax_reason:product.tax_reason ?? "",
      tax_reference:product.tax_reference ?? "",
      inventory_account_id:product.inventory_account_id ?? null,
      purchase_account_id:product.purchase_account_id ?? null,
      cogs_account_id:product.cogs_account_id ?? null,
    } : blank());
  }, [open, product]);

  const update = (key: string, value: unknown) => setForm((current) => ({...current, [key]: value}));
  const changeItemType = (value: ItemType) => setForm((current) => ({...current, item_type:value, group_code:"", group_name:"", subgroup_code:"", subgroup_name:""}));
  const updateGroup = (value: string | undefined) => {
    const code = value ?? "";
    const group = groups.find((item) => item.code === code);
    setForm((current) => ({...current, group_code:code, group_name:group?.name ?? "", subgroup_code:"", subgroup_name:""}));
  };
  const updateSubgroup = (value: string | undefined) => {
    const code = value ?? "";
    const group = groups.find((item) => item.code === form.group_code);
    const sub = (group?.subgroups ?? []).find((item) => item.code === code);
    setForm((current) => ({...current, subgroup_code:code, subgroup_name:sub?.name ?? ""}));
  };
  const valid = form.code.trim() && form.name.trim() && form.group_code && (!subgroupRequired || form.subgroup_code) && form.uom.trim() && form.usage_uom.trim() && Number(form.conversion) > 0 && Number(form.minimum_stock) >= 0 && Number(form.cost_price) >= 0 && Number(form.selling_price) >= 0 && (!form.is_taxable || Number(form.tax_rate) > 0);

  const submit = () => {
    const payload = {
      ...form,
      code:form.code.trim(), name:form.name.trim(),
      uom:form.uom.trim(), usage_uom:form.usage_uom.trim(),
      conversion:Number(form.conversion),
      minimum_stock:Number(form.minimum_stock),
      cost_price:Number(form.cost_price),
      selling_price:Number(form.selling_price),
      tax_rate:Number(form.tax_rate),
      tax_reason:form.tax_reason || null,
      tax_reference:form.tax_reference || null,
    };
    if (product) {
      const { code: _unchangedCode, ...rest } = payload;
      onSubmit(rest);
      return;
    }
    onSubmit(payload);
  };

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-3xl">
      <DialogHeader><DialogTitle>{product ? "Edit Product" : "New Product"}</DialogTitle></DialogHeader>
      <DialogBody>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 font-semibold text-slate-900">Item Type</div>
            <div className="grid grid-cols-2 gap-2">
              {(["BUY", "SELL"] as ItemType[]).map((value) => (
                <button key={value} type="button" onClick={() => changeItemType(value)} className={`h-10 rounded-md border px-3 text-sm font-medium transition-colors ${form.item_type === value ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"}`}>{value === "BUY" ? "Buy Item" : "Sell Item"}</button>
              ))}
            </div>
            {!product && <span className="mt-1 block text-xs font-normal text-slate-500">{form.item_type === "BUY" ? "Purchased items: use Purchase Requisition / Market List, received into inventory." : "Sales items (food, beverage, room, service): recorded with cost & selling price instead of stock."}</span>}
          </div>
          <label className="col-span-2 text-sm font-medium">Product Code
            <Input className="mt-1" disabled={Boolean(product)} maxLength={20} value={form.code} placeholder="Kombinasi unik: HURUF+ANGKA, ex: MARG200, BRE-100, ROOM-DLX" onChange={(event) => update("code", event.target.value)} />
          </label>
          <label className="col-span-2 text-sm font-medium">Product Name
            <Input className="mt-1" value={form.name} placeholder="Ex: Margarine, Susu UHT, Nasi Goreng, Deluxe Room" onChange={(event) => update("name", event.target.value)} />
          </label>
          <label className="col-span-2 text-sm font-medium">Group
            <SearchableSelect className="mt-1" label="Group" value={form.group_code} required placeholder="Type group code or name..." options={groupOptions} onChange={updateGroup} />
          </label>
          <label className="col-span-2 text-sm font-medium">Sub Group
            <SearchableSelect className="mt-1" label="Sub Group" value={form.subgroup_code || undefined} required={subgroupRequired} disabled={!form.group_code} placeholder={form.group_code ? (subgroupRequired ? "Type subgroup code or name..." : "Optional for SELL items...") : "Select Group first"} options={subGroupOptions} onChange={updateSubgroup} />
          </label>
          <label className="text-sm font-medium">Purchase UOM
            <Input className="mt-1" list="purchase-uom-options" value={form.uom} placeholder="Select or type UOM" onChange={(event) => update("uom", event.target.value)} />
            <datalist id="purchase-uom-options">{UOMS.map((uom) => <option key={uom} value={uom}/>)}</datalist>
          </label>
          <label className="text-sm font-medium">Usage UOM
            <Input className="mt-1" list="usage-uom-options" value={form.usage_uom} placeholder="Select or type UOM" onChange={(event) => update("usage_uom", event.target.value)} />
            <datalist id="usage-uom-options">{UOMS.map((uom) => <option key={uom} value={uom}/>)}</datalist>
          </label>
          <label className="text-sm font-medium">Conversion
            <Input className="mt-1" type="number" min="0.0001" step="0.0001" value={form.conversion} placeholder="1" onChange={(event) => update("conversion", Number(event.target.value))} />
          </label>
          <label className="text-sm font-medium">Minimum Stock
            <Input className="mt-1" type="number" min="0" step="0.01" value={form.minimum_stock} placeholder="0" onChange={(event) => update("minimum_stock", Number(event.target.value))} />
            <span className="mt-1 block text-xs font-normal text-slate-500">Dipakai sebagai batas notifikasi reorder. Tidak ditampilkan sebagai kolom min/max di Stock List.</span>
          </label>
          <label className="text-sm font-medium">Cost Price
            <Input className="mt-1" type="number" min="0" step="1000" value={form.cost_price} placeholder="0" onChange={(event) => update("cost_price", Number(event.target.value))} />
          </label>
          <label className="text-sm font-medium">Selling Price
            <Input className="mt-1" type="number" min="0" step="1000" value={form.selling_price} placeholder="0" onChange={(event) => update("selling_price", Number(event.target.value))} />
          </label>
          <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 font-semibold text-slate-900">Direct COA Mapping</div>
            <div className="grid grid-cols-2 gap-4">
              {COA_FIELDS.map(([label, key, help]) => <div key={key}><SearchableSelect label={label} value={form[key] === null || form[key] === undefined ? undefined : String(form[key])} placeholder="Type COA code or name..." options={(accounts.data ?? []).map((account:any) => ({id:String(account.id), label:`${account.code} — ${account.name}`, keywords:[account.code, account.name]}))} onChange={(value) => update(key, value ? Number(value) : null)} /><span className="mt-1 block text-xs font-normal text-slate-500">{help}</span></div>)}
            </div>
          </div>
          <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 font-semibold text-slate-900">PPN / Tax Profile</div>
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm font-medium">Tax Treatment
                <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.tax_category} onChange={(event) => update("tax_category", event.target.value)}>{TAX_CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                <span className="mt-1 block text-xs font-normal text-slate-500">{selectedTax?.help}</span>
              </label>
              <label className="text-sm font-medium">PPN Rate (%)
                <Input className="mt-1" type="number" min="0" max="100" step="0.01" value={form.is_taxable ? form.tax_rate : 0} disabled={!form.is_taxable} placeholder="0" onChange={(event) => update("tax_rate", Number(event.target.value))} />
              </label>
              <label className="col-span-2 flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" checked={form.is_taxable} className="h-4 w-4" onChange={(event) => update("is_taxable", event.target.checked)} /> Item kena PPN
              </label>
              <label className="col-span-2 text-sm font-medium">Tax Reason / Notes
                <Input className="mt-1" placeholder="Contoh: kebutuhan pokok / standard taxable" value={form.tax_reason} onChange={(event) => update("tax_reason", event.target.value)} />
              </label>
              <label className="col-span-2 text-sm font-medium">Tax Reference
                <Input className="mt-1" placeholder="Referensi aturan / memo Finance" value={form.tax_reference} onChange={(event) => update("tax_reference", event.target.value)} />
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

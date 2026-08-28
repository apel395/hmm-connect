import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import type { Product, TaxCategory } from "../types";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";

const UOMS = ["Kg", "Gram", "Liter", "Ml", "Bottle", "Pcs", "Pack", "Box", "Can", "Roll", "Meter", "Set"];
const TAX_CATEGORIES: { value: TaxCategory; label: string; help: string }[] = [
  { value: "REVIEW_REQUIRED", label: "Review Required", help: "Belum diklasifikasikan. Finance harus menetapkan perlakuan PPN sebelum dokumen dilanjutkan." },
  { value: "STANDARD", label: "Standard PPN", help: "Item kena PPN dengan tarif default pada Item Master." },
  { value: "EXEMPT", label: "PPN Dibebaskan", help: "Item mendapat fasilitas pembebasan PPN." },
  { value: "NON_VAT", label: "Non PPN", help: "Item bukan objek PPN untuk penggunaan transaksi ini." },
  { value: "SPECIAL", label: "Perlakuan Khusus", help: "Gunakan untuk item dengan perlakuan pajak khusus dan isi alasan/referensi." },
];
const DEFAULT_CONVERSION: Record<string, { usage: string; conversion: number }> = {
  Kg:{usage:"Gram",conversion:1000}, Gram:{usage:"Gram",conversion:1}, Liter:{usage:"Ml",conversion:1000},
  Ml:{usage:"Ml",conversion:1}, Bottle:{usage:"Ml",conversion:600}, Box:{usage:"Pcs",conversion:1},
  Pack:{usage:"Pcs",conversion:1}, Pcs:{usage:"Pcs",conversion:1}, Can:{usage:"Pcs",conversion:1},
  Roll:{usage:"Meter",conversion:1}, Meter:{usage:"Meter",conversion:1}, Set:{usage:"Set",conversion:1},
};

interface Props {
  open: boolean;
  product?: Product | null;
  products?: Product[];
  loading?: boolean;
  onClose: () => void;
  onSubmit: (payload: any) => void;
}

const blank = () => ({
  code:"", name:"", group_code:"", group_name:"", subgroup_code:"", subgroup_name:"",
  uom:"", usage_uom:"", conversion:1, minimum_stock:0,
  tax_category:"REVIEW_REQUIRED" as TaxCategory,
  is_taxable:false,
  tax_rate:0,
  tax_reason:"",
  tax_reference:"",
  inventory_account_id:null as number|null,
  purchase_account_id:null as number|null,
  cogs_account_id:null as number|null,
});

export default function ProductForm({ open, product, products = [], loading, onClose, onSubmit }: Props) {
  const [form, setForm] = useState(blank());
  const accounts = useQuery({queryKey:["product-coa-lookup"],queryFn:()=>getAccountLookup({is_active:true,is_posting:true})});

  const groups = useMemo(() => {
    const map = new Map<string, { code:string; name:string }>();
    products.forEach((item) => {
      if (item.group_code && item.group_name) map.set(item.group_code, {code:item.group_code, name:item.group_name});
    });
    if (product?.group_code && product.group_name) map.set(product.group_code, {code:product.group_code, name:product.group_name});
    return [...map.values()].sort((a,b) => a.code.localeCompare(b.code));
  }, [products, product]);

  const subGroups = useMemo(() => {
    const map = new Map<string, { code:string; name:string }>();
    products.filter((item) => item.group_code === form.group_code).forEach((item) => {
      if (item.subgroup_code && item.subgroup_name) map.set(item.subgroup_code, {code:item.subgroup_code, name:item.subgroup_name});
    });
    if (product?.group_code === form.group_code && product.subgroup_code && product.subgroup_name) {
      map.set(product.subgroup_code, {code:product.subgroup_code, name:product.subgroup_name});
    }
    return [...map.values()].sort((a,b) => a.code.localeCompare(b.code));
  }, [products, product, form.group_code]);

  useEffect(() => {
    if (!open) return;
    setForm(product ? {
      code:product.code, name:product.name, group_code:product.group_code, group_name:product.group_name,
      subgroup_code:product.subgroup_code, subgroup_name:product.subgroup_name,
      uom:product.uom, usage_uom:product.usage_uom, conversion:Number(product.conversion),
      minimum_stock:Number(product.minimum_stock ?? 0),
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

  const update = (key:string, value:unknown) => setForm((current) => ({...current, [key]:value}));
  const selectedTax = TAX_CATEGORIES.find((item) => item.value === form.tax_category);
  const valid = form.code.trim() && form.name.trim() && form.group_code && form.subgroup_code && form.uom.trim() && form.usage_uom.trim() && Number(form.minimum_stock) >= 0 && (!form.is_taxable || Number(form.tax_rate) > 0);

  const changeTaxCategory = (value: TaxCategory) => {
    const taxable = value === "STANDARD" || value === "SPECIAL";
    setForm((current) => ({
      ...current,
      tax_category:value,
      is_taxable:taxable ? current.is_taxable : false,
      tax_rate:taxable ? current.tax_rate : 0,
    }));
  };

  const changePurchaseUom = (value: string) => {
    const preset = DEFAULT_CONVERSION[value];
    setForm((current) => ({
      ...current,
      uom:value,
      usage_uom:preset?.usage ?? current.usage_uom,
      conversion:preset?.conversion ?? current.conversion,
    }));
  };

  const submit = () => {
    const payload = {
      ...form,
      code:form.code.trim(),
      name:form.name.trim(),
      uom:form.uom.trim(),
      usage_uom:form.usage_uom.trim(),
      conversion:Number(form.conversion),
      minimum_stock:Number(form.minimum_stock),
      tax_rate:Number(form.tax_rate),
      tax_reason:form.tax_reason || null,
      tax_reference:form.tax_reference || null,
    };
    if (product) {
      const { code: _unchangedCode, ...updatePayload } = payload;
      onSubmit(updatePayload);
      return;
    }
    onSubmit(payload);
  };

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-3xl">
      <DialogHeader><DialogTitle>{product ? "Edit Product" : "New Product"}</DialogTitle></DialogHeader>
      <DialogBody><div className="grid grid-cols-2 gap-4">
        <label className="text-sm font-medium">Product Code
          <Input className="mt-1" disabled={Boolean(product)} maxLength={20} value={form.code} onChange={(event) => update("code", event.target.value)} />
        </label>
        <label className="text-sm font-medium">Product Name
          <Input className="mt-1" autoFocus value={form.name} onChange={(event) => update("name", event.target.value)} />
        </label>
        <label className="text-sm font-medium">Group
          <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.group_code} onChange={(event) => {
            const group = groups.find((item) => item.code === event.target.value);
            setForm((current) => ({...current, group_code:group?.code ?? "", group_name:group?.name ?? "", subgroup_code:"", subgroup_name:""}));
          }}>
            <option value="">Select Group</option>{groups.map((group) => <option key={group.code} value={group.code}>{group.code} - {group.name}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">Sub Group
          <select disabled={!form.group_code} className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100" value={form.subgroup_code} onChange={(event) => {
            const subgroup = subGroups.find((item) => item.code === event.target.value);
            setForm((current) => ({...current, subgroup_code:subgroup?.code ?? "", subgroup_name:subgroup?.name ?? ""}));
          }}>
            <option value="">{form.group_code ? "Select Sub Group" : "Select Group first"}</option>{subGroups.map((item) => <option key={item.code} value={item.code}>{item.code} - {item.name}</option>)}
          </select>
          {form.subgroup_name && <span className="mt-1 block text-xs font-normal text-slate-500">Market List eligibility is automatic: only VEGETABLES and FRUIT use Market List; all other subgroups use Purchase Requisition.</span>}
        </label>
        <label className="text-sm font-medium">Purchase UOM
          <Input className="mt-1" list="purchase-uom-options" value={form.uom} placeholder="Select or type UOM" onChange={(event) => changePurchaseUom(event.target.value)} />
          <datalist id="purchase-uom-options">{UOMS.map((uom) => <option key={uom} value={uom}/>)}</datalist>
        </label>
        <label className="text-sm font-medium">Usage UOM
          <Input className="mt-1" list="usage-uom-options" value={form.usage_uom} placeholder="Select or type UOM" onChange={(event) => update("usage_uom", event.target.value)} />
          <datalist id="usage-uom-options">{UOMS.map((uom) => <option key={uom} value={uom}/>)}</datalist>
        </label>
        <label className="text-sm font-medium">Conversion
          <Input className="mt-1" type="number" min="0.0001" step="0.0001" value={form.conversion} onChange={(event) => update("conversion", Number(event.target.value))}/>
        </label>
        <label className="text-sm font-medium">Minimum Stock
          <Input className="mt-1" type="number" min="0" step="0.01" value={form.minimum_stock} onChange={(event) => update("minimum_stock", Number(event.target.value))}/>
          <span className="mt-1 block text-xs font-normal text-slate-500">Dipakai sebagai batas notifikasi reorder. Tidak ditampilkan sebagai kolom min/max di Stock List.</span>
        </label>

        <div className="col-span-2 mt-2 rounded-lg border border-emerald-200 bg-emerald-50/40 p-4">
          <div className="mb-3">
            <div className="font-semibold text-slate-900">Direct COA Mapping</div>
            <div className="text-xs text-slate-500">COA is copied to transaction and journal snapshots. Existing posted journals never follow later master changes.</div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              ["Inventory Asset COA","inventory_account_id","Used when this item is received into a warehouse."],
              ["Consumption / Expense COA","purchase_account_id","Used for direct-use supplier invoices."],
              ["COGS / Issue COA","cogs_account_id","Used when warehouse stock is issued or consumed."],
            ].map(([label,key,help])=><label key={key} className="text-sm font-medium">{label}
              <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={(form as any)[key] ?? ""} onChange={(event)=>update(key,event.target.value?Number(event.target.value):null)}>
                <option value="">Not configured</option>
                {accounts.data?.map((account)=><option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}
              </select>
              <span className="mt-1 block text-xs font-normal text-slate-500">{help}</span>
            </label>)}
          </div>
        </div>

        <div className="col-span-2 mt-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="mb-3">
            <div className="font-semibold text-slate-900">PPN / Tax Profile</div>
            <div className="text-xs text-slate-500">Default pajak dari Item Master akan di-snapshot ke PR, PO, Receiving, dan Supplier Invoice.</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm font-medium">Tax Treatment
              <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.tax_category} onChange={(event) => changeTaxCategory(event.target.value as TaxCategory)}>
                {TAX_CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
              <span className="mt-1 block text-xs font-normal text-slate-500">{selectedTax?.help}</span>
            </label>
            <div className="space-y-3">
              <label className="flex items-center gap-2 pt-1 text-sm font-medium">
                <input type="checkbox" checked={form.is_taxable} disabled={!(["STANDARD", "SPECIAL"] as TaxCategory[]).includes(form.tax_category)} onChange={(event) => setForm((current) => ({...current, is_taxable:event.target.checked, tax_rate:event.target.checked ? current.tax_rate : 0}))}/>
                Item kena PPN
              </label>
              <label className="block text-sm font-medium">Default PPN Rate (%)
                <Input className="mt-1" type="number" min="0" max="100" step="0.01" disabled={!form.is_taxable} value={form.tax_rate} onChange={(event) => update("tax_rate", Number(event.target.value))}/>
              </label>
            </div>
            <label className="text-sm font-medium">Tax Reason / Notes
              <Input className="mt-1" placeholder="Contoh: kebutuhan pokok / standard taxable" value={form.tax_reason} onChange={(event) => update("tax_reason", event.target.value)} />
            </label>
            <label className="text-sm font-medium">Tax Reference
              <Input className="mt-1" placeholder="Referensi aturan / memo Finance" value={form.tax_reference} onChange={(event) => update("tax_reference", event.target.value)} />
            </label>
          </div>
        </div>
      </div></DialogBody>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={!valid} loading={loading} onClick={submit}>Save</Button></DialogFooter></DialogContent>
  </Dialog>;
}

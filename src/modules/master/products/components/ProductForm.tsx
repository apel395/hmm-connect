import { useEffect, useMemo, useState } from "react";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import type { Product } from "../types";

const UOMS = ["Kg", "Gram", "Liter", "Ml", "Bottle", "Pcs", "Pack", "Box", "Can", "Roll", "Meter", "Set"];
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
  name:"", group_code:"", group_name:"", subgroup_code:"", subgroup_name:"",
  uom:"", usage_uom:"", conversion:1,
});

export default function ProductForm({ open, product, products = [], loading, onClose, onSubmit }: Props) {
  const [form, setForm] = useState(blank());

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
      name:product.name, group_code:product.group_code, group_name:product.group_name,
      subgroup_code:product.subgroup_code, subgroup_name:product.subgroup_name,
      uom:product.uom, usage_uom:product.usage_uom, conversion:Number(product.conversion),
    } : blank());
  }, [open, product]);

  const update = (key:string, value:unknown) => setForm((current) => ({...current, [key]:value}));
  const valid = form.name.trim() && form.group_code && form.subgroup_code && form.uom && form.usage_uom;

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-2xl">
      <DialogHeader><DialogTitle>{product ? "Edit Product" : "New Product"}</DialogTitle></DialogHeader>
      <DialogBody><div className="grid grid-cols-2 gap-4">
        <label className="col-span-2 text-sm font-medium">Product Name
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
        </label>
        <label className="text-sm font-medium">Purchase UOM
          <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.uom} onChange={(event) => {
            const value = event.target.value; const preset = DEFAULT_CONVERSION[value];
            setForm((current) => ({...current, uom:value, usage_uom:preset?.usage ?? "", conversion:preset?.conversion ?? 1}));
          }}><option value="">Select Purchase UOM</option>{UOMS.map((uom) => <option key={uom}>{uom}</option>)}</select>
        </label>
        <label className="text-sm font-medium">Usage UOM
          <select className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={form.usage_uom} onChange={(event) => update("usage_uom", event.target.value)}><option value="">Select Usage UOM</option>{UOMS.map((uom) => <option key={uom}>{uom}</option>)}</select>
        </label>
        <label className="text-sm font-medium">Conversion
          <Input className="mt-1" type="number" min="0.0001" step="0.0001" value={form.conversion} onChange={(event) => update("conversion", Number(event.target.value))}/>
        </label>
      </div></DialogBody>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={!valid} loading={loading} onClick={() => onSubmit({...form, conversion:Number(form.conversion)})}>Save</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}

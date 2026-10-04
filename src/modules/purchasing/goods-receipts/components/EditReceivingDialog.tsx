import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { useUpdateGoodsReceipt } from "../hooks/useGoodsReceipts";
import type { GoodsReceipt } from "../types";

function localDateTime(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function EditReceivingDialog({ open, receipt, onClose }:{ open:boolean; receipt:GoodsReceipt; onClose:()=>void }) {
  const { data: warehouses = [] } = useWarehouses();
  const update = useUpdateGoodsReceipt();
  const [receivedAt,setReceivedAt]=useState("");
  const [reference,setReference]=useState("");
  const [destination,setDestination]=useState<"WAREHOUSE"|"DIRECT_USE">("WAREHOUSE");
  const [warehouseId,setWarehouseId]=useState<number|null>(null);
  const [notes,setNotes]=useState("");
  const [items,setItems]=useState<any[]>([]);

  useEffect(()=>{
    if(!open)return;
    setReceivedAt(localDateTime(receipt.received_at));
    setReference(receipt.external_reference ?? receipt.delivery_note_number ?? "");
    setDestination(receipt.destination_type === "DIRECT_USE" ? "DIRECT_USE" : "WAREHOUSE");
    setWarehouseId(receipt.warehouse_id ?? null);
    setNotes(receipt.notes ?? "");
    setItems(receipt.items.map(item=>({
      item_id:item.id, product_name:item.product_name, product_code:item.product_code, uom:item.uom,
      quantity:Number(item.quantity), unit_cost:Number(item.unit_cost),
      is_taxable:Boolean(item.is_taxable), tax_rate:Number(item.tax_rate ?? 0),
    })));
  },[open,receipt]);

  const patch=(id:number,values:any)=>setItems(current=>current.map(item=>item.item_id===id?{...item,...values}:item));
  const save=async()=>{
    if(!receivedAt)return toast.error("Receipt date is required");
    if(receivedAt < "2026-01-01T00:00")return toast.error("Receiving dated before 2026 is excluded from stock.");
    if(destination==="WAREHOUSE"&&!warehouseId)return toast.error("Warehouse is required");
    if(items.some(item=>item.quantity<=0||item.unit_cost<=0))return toast.error("Quantity and unit cost must be greater than zero");
    try{
      await update.mutateAsync({
        id:receipt.id,
        payload:{
          received_at:new Date(receivedAt).toISOString(),
          external_reference:reference.trim()||null,
          destination_type:destination,
          warehouse_id:destination==="WAREHOUSE"?warehouseId:null,
          notes:notes.trim()||null,
          items:items.map(item=>({item_id:item.item_id,quantity:item.quantity,unit_cost:item.unit_cost,is_taxable:item.is_taxable,tax_rate:item.is_taxable?item.tax_rate:0})),
        },
      });
      toast.success("Receiving updated");
      onClose();
    }catch(error){
      const detail=axios.isAxiosError(error)?error.response?.data?.detail:null;
      toast.error(typeof detail==="string"?detail:"Receiving could not be updated");
    }
  };

  const warehouseOptions=warehouses.filter((row:any)=>row.is_active).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}));

  return <Dialog open={open} onOpenChange={value=>!value&&onClose()}>
    <DialogContent className="max-h-[92vh] max-w-6xl overflow-hidden">
      <DialogHeader><DialogTitle>Edit Receiving Report</DialogTitle></DialogHeader>
      <DialogBody className="space-y-4 overflow-y-auto">
        <div className="rounded border bg-slate-50 p-3 text-sm">
          <div className="font-medium">{receipt.receipt_number}</div>
          <div className="text-slate-600">Source {receipt.purchase_order_number ?? "Direct Receiving"} · Supplier {receipt.supplier_name ?? "—"} · BU {receipt.business_unit_name ?? "—"} · Location {receipt.location_name ?? "—"} · Department {receipt.department_name ?? "—"}</div>
          <div className="mt-1 text-xs text-slate-500">Source document and inherited organization dimensions are locked for traceability.</div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">Receipt Date *<input type="datetime-local" data-accounting-date="true" data-min-date="2026-01-01" min="2026-01-01T00:00" className="mt-1 h-10 w-full rounded border px-3" value={receivedAt} onChange={e=>setReceivedAt(e.target.value)}/></label>
          <label className="text-sm">Delivery Note / Reference<input className="mt-1 h-10 w-full rounded border px-3" value={reference} onChange={e=>setReference(e.target.value)}/></label>
          <label className="text-sm">Destination<select className="mt-1 h-10 w-full rounded border px-3" value={destination} onChange={e=>setDestination(e.target.value as any)}><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select></label>
          {destination==="WAREHOUSE"&&<SearchableSelect label="Warehouse" required value={warehouseId ?? undefined} placeholder="Type warehouse code or name..." options={warehouseOptions} onChange={value=>setWarehouseId(value ?? null)}/>} 
        </div>
        <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-3" value={notes} onChange={e=>setNotes(e.target.value)}/></label>
        <div className="overflow-x-auto rounded border">
          <table className="w-full min-w-[820px] text-sm">
            <thead><tr><th className="w-[40%] p-3 text-left">Item</th><th className="w-20">UOM</th><th className="w-32">Qty</th><th className="w-40">Unit Cost</th><th className="w-20">PPN</th><th className="w-28">Rate %</th></tr></thead>
            <tbody>{items.map(item=><tr key={item.item_id} className="border-t">
              <td className="p-3"><div className="font-medium">{item.product_name}</div><div className="text-xs text-slate-500">{item.product_code}</div></td>
              <td className="text-center">{item.uom??"—"}</td>
              <td className="p-2"><input type="number" min="0.01" step="0.01" className="h-9 w-28 rounded border px-2 text-right" value={item.quantity} onChange={e=>patch(item.item_id,{quantity:Number(e.target.value)})}/></td>
              <td className="p-2"><CurrencyInput value={item.unit_cost} onValueChange={value=>patch(item.item_id,{unit_cost:value})}/></td>
              <td className="text-center"><input type="checkbox" checked={item.is_taxable} onChange={e=>patch(item.item_id,{is_taxable:e.target.checked,tax_rate:e.target.checked?(item.tax_rate||11):0})}/></td>
              <td className="p-2"><input type="number" min="0" max="100" step="0.01" disabled={!item.is_taxable} className="h-9 w-24 rounded border px-2 text-right disabled:bg-slate-100" value={item.tax_rate} onChange={e=>patch(item.item_id,{tax_rate:Number(e.target.value)})}/></td>
            </tr>)}</tbody>
          </table>
        </div>
      </DialogBody>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={update.isPending} onClick={save}>Save Changes</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}

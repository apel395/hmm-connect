import "../receiving-lines.css";
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { useQuery } from "@tanstack/react-query";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import QuantityInput from "@/components/form/QuantityInput";
import { Trash2 } from "lucide-react";
import ProductCombobox, { type ProductComboboxOption } from "@/components/form/ProductCombobox";
import SearchableSelect from "@/components/form/SearchableSelect";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { listLocations } from "@/modules/admin/organization/api";
import { useUpdateGoodsReceipt } from "../hooks/useGoodsReceipts";
import type { GoodsReceipt } from "../types";
import ReceivingDestinationField from "./ReceivingDestinationField";
import ReceivingBillingFields from "./ReceivingBillingFields";
import { emptyReceivingBilling, fromReceiptBilling, receivingBillingPayload, validateReceivingBilling } from "../billing";
import { destinationFor, destinationError } from "../destination";

function localDateTime(value: string) {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
const money = (value: number) => value.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function EditReceivingDialog({ open, receipt, onClose }:{ open:boolean; receipt:GoodsReceipt; onClose:()=>void }) {
  const { data: warehouses = [] } = useWarehouses();
  const update = useUpdateGoodsReceipt();
  const [receivedAt,setReceivedAt]=useState("");
  const [reference,setReference]=useState("");
  const [warehouseId,setWarehouseId]=useState<number|null>(null);
  const [locationId,setLocationId]=useState<number|null>(null);
  const [notes,setNotes]=useState("");
  const [billing,setBilling]=useState(emptyReceivingBilling);
  const [items,setItems]=useState<any[]>([]);
  const [productRows,setProductRows]=useState<ProductComboboxOption[]>([]);
  const nextNewId=useRef(0);
  const directReceipt=!receipt.purchase_order_id && !receipt.market_list_id;
  const locations=useQuery({queryKey:["receiving-edit-locations",receipt.business_unit_id],queryFn:()=>listLocations({business_unit_id:receipt.business_unit_id??undefined,is_active:true,assigned_only:true}),enabled:open && directReceipt && !!receipt.business_unit_id});
  const [catalogType,setCatalogType]=useState<"CATERING" | "HOTEL" | "ALL">("ALL");
  const hasWarehouse = items.some(item => destinationFor(item) === "WAREHOUSE");
  const hasDirectUse = items.some(item => destinationFor(item) === "DIRECT_USE" && item.inventory_treatment !== "FIXED_ASSET");
  const expenses=useQuery({queryKey:["receiving-expense-accounts"],queryFn:()=>getAllAccountLookup({account_type:"EXPENSE",is_active:true,is_posting:true}),enabled:open && hasDirectUse});

  useEffect(()=>{
    if(!open)return;
    setReceivedAt(localDateTime(receipt.received_at));
    setReference(receipt.external_reference ?? receipt.delivery_note_number ?? "");
    setWarehouseId(receipt.warehouse_id ?? null);
    setLocationId(receipt.location_id ?? null);
    setNotes(receipt.notes ?? "");
    setBilling(fromReceiptBilling(receipt));
    setCatalogType("ALL");
    setProductRows(receipt.items.map(item=>({id:item.product_id,code:item.product_code,name:item.product_name,uom:item.uom??undefined,catalog_type:item.catalog_type,inventory_treatment:item.inventory_treatment,purchase_account_id:item.purchase_account_id,is_taxable:item.master_is_taxable,tax_rate:item.master_tax_rate})));
    setItems(receipt.items.map(item=>({
      row_key:`existing-${item.id}`,item_id:item.id,original_item_id:item.id,original_product_id:item.product_id,product_id:item.product_id, catalog_type:item.catalog_type, inventory_treatment:item.inventory_treatment, product_name:item.product_name, product_code:item.product_code, uom:item.uom,
      destination_type:item.destination_type ?? (receipt.destination_type === "DIRECT_USE" ? "DIRECT_USE" : "WAREHOUSE"),
      original_destination:item.destination_type ?? (receipt.destination_type === "DIRECT_USE" ? "DIRECT_USE" : "WAREHOUSE"),
      destination_override_reason:item.destination_override_reason ?? null,
      quantity:Number(item.quantity), unit_cost:Number(item.unit_cost), expense_account_id:item.expense_account_id ?? null,
      is_taxable:Boolean(item.master_is_taxable), tax_rate:Number(item.master_tax_rate ?? 0),
    })));
  },[open,receipt]);

  const patch=(key:string,values:any)=>setItems(current=>current.map(item=>item.row_key===key?{...item,...values}:item));
  const addItem=()=>setItems(current=>[...current,{row_key:`new-${++nextNewId.current}`,product_id:0,quantity:1,unit_cost:0,is_taxable:false,tax_rate:0,destination_type:null,destination_override_reason:null,expense_account_id:null}]);
  const subtotal=items.reduce((sum,item)=>sum+Number(item.quantity||0)*Number(item.unit_cost||0),0);
  const tax=items.reduce((sum,item)=>sum+Number(item.quantity||0)*Number(item.unit_cost||0)*(item.is_taxable?Number(item.tax_rate||0):0)/100,0);
  const save=async()=>{
    if(receipt.status!=="DRAFT")return toast.error("Posted receiving requires the correction or return workflow");
    if(!items.length)return toast.error("Keep at least one receiving item");
    if(!receivedAt)return toast.error("Receipt date is required");
    if(receivedAt < "2026-01-01T00:00")return toast.error("Receiving dated before 2026 is excluded from stock.");
    if(hasWarehouse&&!warehouseId)return toast.error("Warehouse is required");
    if(directReceipt&&!locationId)return toast.error("Location is required");
    if(items.some(item=>!item.item_id&&!item.product_id))return toast.error("Choose an item for every new line");
    const routingIssue = items.map(destinationError).find(Boolean);
    if(routingIssue)return toast.error(routingIssue);
    if(items.some(item=>destinationFor(item) === "DIRECT_USE" && item.catalog_type === "HOTEL" && item.inventory_treatment !== "FIXED_ASSET" && !item.expense_account_id))return toast.error("Choose the department expense destination for each Hotel item");
    if(items.some(item=>item.quantity<=0||item.unit_cost<=0))return toast.error("Quantity and unit cost must be greater than zero");
    const billingIssue=validateReceivingBilling(billing,subtotal);
    if(billingIssue)return toast.error(billingIssue);
    try{
      await update.mutateAsync({
        id:receipt.id,
        payload:{
          received_at:new Date(receivedAt).toISOString(),
          ...(directReceipt?{location_id:locationId}:{}),
          external_reference:reference.trim()||null,
          warehouse_id:hasWarehouse?warehouseId:null,
          notes:notes.trim()||null,...receivingBillingPayload(billing),
          items:items.map(item=>({...(item.item_id?{item_id:item.item_id}:{product_id:item.product_id}),destination_type:item.destination_type ?? null,destination_override_reason:item.destination_override_reason || null,expense_account_id:destinationFor(item) === "DIRECT_USE" ? item.expense_account_id : null,quantity:item.quantity,unit_cost:item.unit_cost,is_taxable:item.is_taxable,tax_rate:item.is_taxable?item.tax_rate:0})),
        },
      });
      toast.success(receipt.approval_status==="APPROVED"?"Receiving updated; approval restarted":"Receiving updated");
      onClose();
    }catch(error){
      const detail=axios.isAxiosError(error)?error.response?.data?.detail:null;
      toast.error(typeof detail==="string"?detail:"Receiving could not be updated");
    }
  };

  const warehouseOptions=warehouses.filter((row:any)=>row.is_active && Number(row.location_id) === locationId).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}));

  return <Dialog open={open} onOpenChange={value=>!value&&onClose()}>
      <DialogContent className="max-h-[92vh] max-w-[1440px] overflow-hidden">
      <DialogHeader><DialogTitle>Edit Receiving Report</DialogTitle></DialogHeader>
      <DialogBody className="space-y-4 overflow-y-auto">
        <div className="rounded border bg-slate-50 p-3 text-sm">
          <div className="font-medium">{receipt.receipt_number}</div>
          <div className="text-slate-600">Source {receipt.purchase_order_number ?? "Direct Receiving"} · Supplier {receipt.supplier_name ?? "—"} · BU {receipt.business_unit_name ?? "—"} · Location {receipt.location_name ?? "—"} · Department {receipt.department_name ?? "—"}</div>
          <div className="mt-1 text-xs text-slate-500">{directReceipt?"Direct Receiving location can be corrected before posting; warehouse must belong to the selected location. Business Unit and Department stay locked. Remove or reselect items below.":"Source organization dimensions and item identity follow the PO / Market List. Lines may be removed before posting."}</div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">Receipt Date *<input type="datetime-local" disabled={receipt.source_type === "LIVE"} data-accounting-date="true" data-min-date="2026-01-01" min="2026-01-01T00:00" className="mt-1 h-10 w-full rounded border px-3" value={receivedAt} onChange={e=>setReceivedAt(e.target.value)}/></label>
          <label className="text-sm">Delivery Note / Reference<input className="mt-1 h-10 w-full rounded border px-3" value={reference} onChange={e=>setReference(e.target.value)}/></label>

          {directReceipt&&<SearchableSelect label="Location" required value={locationId??undefined} placeholder="Type location code or name..." options={(locations.data??[]).map(row=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code,row.name]}))} onChange={value=>{setLocationId(value??null);setWarehouseId(null);}}/>}

          {hasWarehouse&&<SearchableSelect label="Warehouse" required value={warehouseId ?? undefined} placeholder="Type warehouse code or name..." options={warehouseOptions} onChange={value=>setWarehouseId(value ?? null)}/>} 
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          {directReceipt && <label className="mb-2 block text-xs">Item catalog <select className="ml-2 rounded border p-2" value={catalogType} onChange={e=>setCatalogType(e.target.value as "CATERING"|"HOTEL"|"ALL")}><option value="ALL">All Buy Items</option><option value="CATERING">Catering Items</option><option value="HOTEL">Hotel Items</option></select></label>}
          <table className="receiving-lines receiving-lines-edit">
            <colgroup><col/><col className="rl-destination"/><col className="rl-unit"/><col className="rl-quantity"/><col className="rl-cost"/><col className="rl-tax-rate"/><col className="rl-amount"/><col className="rl-total"/><col className="rl-action"/></colgroup>
            <thead className="bg-slate-50"><tr><th className="p-2 text-left">Product</th><th>Destination</th><th>UOM</th><th>Qty</th><th className="whitespace-nowrap">Unit Cost</th><th title="Provisional PPN rate; confirmed in AP">PPN %</th><th>PPN</th><th>Line Total</th><th/></tr></thead>
            <tbody>{items.map(item=><tr key={item.row_key} className="border-t">
              <td className="p-2">{!directReceipt?<><div className="font-medium">{item.product_name}</div><div className="text-xs text-slate-500">{item.product_code}</div></>:<ProductCombobox remote catalogType={catalogType==="ALL"?undefined:catalogType} products={productRows} value={item.product_id||undefined} onChange={id=>patch(item.row_key,{product_id:id||0,...!id?{item_id:undefined}:{}})} onSelect={product=>{setProductRows(current=>current.some(row=>row.id===product.id)?current:[...current,product]);patch(item.row_key,{item_id:product.id===item.original_product_id?item.original_item_id:undefined,product_id:product.id,product_name:product.name,product_code:product.code,uom:product.uom,catalog_type:product.catalog_type,inventory_treatment:product.inventory_treatment,expense_account_id:product.purchase_account_id??null,unit_cost:Number(product.reference_cost??product.last_purchase_price??0),destination_type:null,destination_override_reason:null,is_taxable:!!product.is_taxable,tax_rate:Number(product.tax_rate??0)});}}/>}</td>
              <td className="p-2"><ReceivingDestinationField name={item.product_name??"New item"} line={item} onChange={value => patch(item.row_key, value)}/></td>
              <td className="text-center">{item.uom??"—"}</td>
              <td className="p-2"><QuantityInput value={item.quantity} onValueChange={value=>patch(item.row_key,{quantity:value})}/></td>
              <td className="p-2"><CurrencyInput value={item.unit_cost} onValueChange={value=>patch(item.row_key,{unit_cost:value})}/>{destinationFor(item)==="DIRECT_USE" && item.inventory_treatment!=="FIXED_ASSET" && <label className="block text-xs">Expense destination<select aria-label={`Expense destination for ${item.product_name??"new item"}`} className="w-full rounded border p-1" value={item.expense_account_id??""} onChange={e=>patch(item.row_key,{expense_account_id:Number(e.target.value)||null})}><option value="">{item.catalog_type==="HOTEL"?"Choose department expense":"Item expense mapping"}</option>{expenses.data?.map(account=><option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select></label>}</td>
              <td className="p-2"><span title="From Item Master" className="inline-block w-14 text-right tabular-nums">{item.is_taxable?Number(item.tax_rate??0):0}%</span></td>
              <td className="text-right">{money(Number(item.quantity||0)*Number(item.unit_cost||0)*(item.is_taxable?Number(item.tax_rate||0):0)/100)}</td>
              <td className="text-right font-medium">{money(Number(item.quantity||0)*Number(item.unit_cost||0)*(1+(item.is_taxable?Number(item.tax_rate||0):0)/100))}</td>
              <td className="p-2"><Button size="sm" variant="ghost" disabled={items.length<=1||update.isPending} aria-label={`Remove item ${item.product_name??"new line"}`} title="Remove item" onClick={()=>setItems(current=>current.filter(row=>row.row_key!==item.row_key))}><Trash2 size={14}/></Button></td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className="flex items-start justify-between">
          {directReceipt ? <Button variant="outline" onClick={addItem}>Add Item</Button> : <span/>}
          <div className="min-w-64 space-y-1 text-right text-xs tabular-nums">
            <div className="flex justify-between gap-8"><span>Subtotal</span><strong>{money(subtotal)}</strong></div>
            <div className="flex justify-between gap-8"><span>PPN</span><strong>{money(tax)}</strong></div>
            <div className="flex justify-between gap-8 border-t pt-2 text-sm"><span>Grand Total</span><strong>{money(subtotal+tax)}</strong></div>
          </div>
        </div>
        <ReceivingBillingFields value={billing} onChange={setBilling} subtotal={subtotal} tax={tax} open={open}/>
         <label className="block text-xs font-medium text-slate-700">Notes<textarea className="mt-1 min-h-20 w-full rounded-md border p-2 text-[13px]" value={notes} onChange={e=>setNotes(e.target.value)}/></label>
      </DialogBody>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={update.isPending} onClick={save}>{receipt.approval_status==="APPROVED"?"Save & Restart Approval":"Save Changes"}</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}


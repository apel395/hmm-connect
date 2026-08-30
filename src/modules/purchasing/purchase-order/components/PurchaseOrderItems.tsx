import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import CurrencyInput from "@/components/form/CurrencyInput";
import ProductCombobox, { type ProductComboboxOption } from "@/components/form/ProductCombobox";
import QuantityInput from "@/components/form/QuantityInput";
import type { SupplierProduct } from "@/modules/master/suppliers/typesSupplierProduct";

export interface PurchaseOrderItemRow {
  product_id?:number; product_code?:string; product_name?:string; description?:string; uom?:string;
  requested_quantity?:number; remaining_quantity?:number; quantity:number; unit_price:number;
  purchase_requisition_item_id?:number|null; source_pr_number?:string;
}
interface ProductOption extends ProductComboboxOption { id:number; code:string; name:string; description?:string|null; uom:string }
interface Props { items:PurchaseOrderItemRow[]; products?:ProductOption[]; supplierProducts?:SupplierProduct[]; fromRequisition:boolean; editing?:boolean; onChange:(rows:PurchaseOrderItemRow[])=>void; onProductLoaded?:(product:ProductOption)=>void }
const money=(value:number)=>value.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});

export default function PurchaseOrderItems({items,products=[],supplierProducts=[],fromRequisition,editing=false,onChange,onProductLoaded}:Props) {
  const update = (index:number, values:Partial<PurchaseOrderItemRow>) => onChange(items.map((row,rowIndex) => rowIndex === index ? {...row,...values} : row));
  const selectProduct = (index:number, product:ProductOption) => {
    onProductLoaded?.(product);
    update(index,{product_id:product.id,product_code:product.code,product_name:product.name,description:product.description ?? "",uom:product.uom ?? ""});
  };

  return <div className="space-y-4">
    <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="table-grid min-w-[1120px] w-full table-fixed text-sm">
      <thead className="bg-slate-50"><tr>{fromRequisition && <th className="w-32 p-3 text-left">Source PR</th>}{fromRequisition && <th className="w-28 p-3 text-left">Item Code</th>}<th className="w-44 p-3 text-left">Item Name</th><th className="w-48 p-3 text-left">Description</th>{fromRequisition && <th className="w-28 p-3 text-right">Requested Qty</th>}{fromRequisition && <th className="w-28 p-3 text-right">Remaining Qty</th>}<th className="w-32 p-3 text-right">{fromRequisition ? "Selected Qty" : "Quantity"}</th><th className="w-24 p-3 text-left">UOM</th><th className="w-44 p-3 text-right">Unit Cost</th><th className="w-40 p-3 text-right">Line Total</th>{!fromRequisition && <th className="w-24"/>}</tr></thead>
      <tbody>{items.map((row,index) => {const recommendation=supplierProducts.find((item)=>item.product_id===row.product_id&&item.is_active);const variance=recommendation&&recommendation.last_price>0?(row.unit_price-recommendation.last_price)/recommendation.last_price:0;return <tr key={row.purchase_requisition_item_id ?? index} className="border-t">
        {fromRequisition && <td className="p-3 font-medium">{row.source_pr_number || "—"}</td>}
        {fromRequisition && <td className="p-3">{row.product_code || "—"}</td>}
        <td className="p-2">{fromRequisition ? row.product_name : <ProductCombobox value={row.product_id} products={products} remote requireTaxReady onChange={()=>{}} onSelect={(product)=>selectProduct(index, product as ProductOption)}/>}</td>
        <td className="p-2">{fromRequisition ? (row.description || "—") : <Input value={row.description ?? ""} onChange={(event) => update(index,{description:event.target.value})}/>}</td>
        {fromRequisition && <td className="p-3 text-right tabular-nums">{row.requested_quantity}</td>}{fromRequisition && <td className="p-3 text-right tabular-nums">{row.remaining_quantity}</td>}
        <td className="p-2"><QuantityInput value={row.quantity} min={0} max={fromRequisition && !editing ? row.remaining_quantity : undefined} step={0.01} onValueChange={(value) => update(index,{quantity:value})}/></td>
        <td className="p-3">{row.uom || "—"}</td>
        <td className="p-2 tabular-nums"><CurrencyInput value={row.unit_price} onValueChange={(value) => update(index,{unit_price:value})}/>{recommendation&&<div className={`mt-1 text-[11px] ${Math.abs(variance)>0.1?"font-medium text-amber-700":"text-slate-500"}`}>Last: {money(recommendation.last_price)}{recommendation.preferred?" · preferred":""}{Math.abs(variance)>0.1?` · ${variance>0?"+":""}${(variance*100).toFixed(0)}%`:""}</div>}</td>
        <td className="p-3 text-right font-medium tabular-nums whitespace-nowrap">{money(row.quantity * row.unit_price)}</td>
        {!fromRequisition && <td className="p-2"><Button type="button" variant="danger" size="sm" onClick={() => onChange(items.filter((_,rowIndex) => rowIndex !== index))}>Remove</Button></td>}
      </tr>})}</tbody>
    </table></div>
    {!fromRequisition && <Button type="button" onClick={() => onChange([...items,{quantity:1,unit_price:0,purchase_requisition_item_id:null}])}>Add Item</Button>}
  </div>;
}

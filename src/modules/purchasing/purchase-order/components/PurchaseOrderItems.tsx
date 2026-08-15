import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Badge from "@/components/ui/Badge";
import CurrencyInput from "@/components/form/CurrencyInput";
import ProductCombobox, { type ProductComboboxOption } from "@/components/form/ProductCombobox";
import QuantityInput from "@/components/form/QuantityInput";

export interface PurchaseOrderItemRow {
  product_id?:number; product_code?:string; product_name?:string; description?:string; uom?:string;
  requested_quantity?:number; remaining_quantity?:number; quantity:number; unit_price:number;
  purchase_requisition_item_id?:number|null;
  tax_category?:string; is_taxable?:boolean; tax_rate?:number; tax_amount?:number;
}
interface ProductOption extends ProductComboboxOption { id:number; code:string; name:string; description?:string|null; uom:string }
interface Props { items:PurchaseOrderItemRow[]; products?:ProductOption[]; fromRequisition:boolean; editing?:boolean; onChange:(rows:PurchaseOrderItemRow[])=>void; onProductLoaded?:(product:ProductOption)=>void }

const money=(value:number)=>value.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const lineTax=(row:PurchaseOrderItemRow)=>row.is_taxable ? row.quantity*row.unit_price*Number(row.tax_rate??0)/100 : 0;
const taxBadge=(row:PurchaseOrderItemRow)=>{
  if(String(row.tax_category??"").toUpperCase()==="REVIEW_REQUIRED") return <Badge variant="warning">Review Required</Badge>;
  if(row.is_taxable) return <Badge variant="warning">PPN {Number(row.tax_rate??0)}%</Badge>;
  return <Badge variant="outline">Non-PPN</Badge>;
};

export default function PurchaseOrderItems({items,products=[],fromRequisition,editing=false,onChange,onProductLoaded}:Props) {
  const update = (index:number, values:Partial<PurchaseOrderItemRow>) => onChange(items.map((row,rowIndex) => rowIndex === index ? {...row,...values} : row));
  const selectProduct = (index:number, product:ProductOption) => {
    onProductLoaded?.(product);
    update(index,{
      product_id:product.id,
      product_code:product.code,
      product_name:product.name,
      description:product.description ?? "",
      uom:product.uom ?? "",
      tax_category:product.tax_category,
      is_taxable:Boolean(product.is_taxable),
      tax_rate:Boolean(product.is_taxable) ? Number(product.tax_rate ?? 0) : 0,
    });
  };

  return <div className="space-y-4">
    <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="table-grid min-w-[1320px] w-full table-fixed text-sm">
      <thead className="bg-slate-50"><tr>{fromRequisition && <th className="w-28 p-3 text-left">Item Code</th>}<th className="w-44 p-3 text-left">Item Name</th><th className="w-48 p-3 text-left">Description</th>{fromRequisition && <th className="w-28 p-3 text-right">Requested Qty</th>}{fromRequisition && <th className="w-28 p-3 text-right">Remaining Qty</th>}<th className="w-32 p-3 text-right">{fromRequisition ? "Selected Qty" : "Quantity"}</th><th className="w-24 p-3 text-left">UOM</th><th className="w-40 p-3 text-right">Unit Cost</th><th className="w-40 p-3 text-right">Subtotal</th><th className="w-36 p-3 text-left">Tax Status</th><th className="w-32 p-3 text-right">PPN</th><th className="w-40 p-3 text-right">Line Total</th>{!fromRequisition && <th className="w-24"/>}</tr></thead>
      <tbody>{items.map((row,index) => {const subtotal=row.quantity*row.unit_price;const tax=lineTax(row);return <tr key={row.purchase_requisition_item_id ?? index} className="border-t">
        {fromRequisition && <td className="p-3">{row.product_code || "—"}</td>}
        <td className="p-2">{fromRequisition ? row.product_name : <ProductCombobox value={row.product_id} products={products} remote onChange={()=>{}} onSelect={(product)=>selectProduct(index, product as ProductOption)}/>}</td>
        <td className="p-2">{fromRequisition ? (row.description || "—") : <Input value={row.description ?? ""} onChange={(event) => update(index,{description:event.target.value})}/>}</td>
        {fromRequisition && <td className="p-3 text-right tabular-nums">{row.requested_quantity}</td>}{fromRequisition && <td className="p-3 text-right tabular-nums">{row.remaining_quantity}</td>}
        <td className="p-2"><QuantityInput value={row.quantity} min={0} max={fromRequisition && !editing ? row.remaining_quantity : undefined} step={0.01} onValueChange={(value) => update(index,{quantity:value})}/></td>
        <td className="p-3">{row.uom || "—"}</td>
        <td className="p-2 tabular-nums"><CurrencyInput value={row.unit_price} onValueChange={(value) => update(index,{unit_price:value})}/></td>
        <td className="p-3 text-right tabular-nums whitespace-nowrap">{money(subtotal)}</td>
        <td className="p-3">{taxBadge(row)}</td>
        <td className="p-3 text-right tabular-nums whitespace-nowrap">{money(tax)}</td>
        <td className="p-3 text-right font-medium tabular-nums whitespace-nowrap">{money(subtotal+tax)}</td>
        {!fromRequisition && <td className="p-2"><Button type="button" variant="danger" size="sm" onClick={() => onChange(items.filter((_,rowIndex) => rowIndex !== index))}>Remove</Button></td>}
      </tr>})}</tbody>
    </table></div>
    {!fromRequisition && <Button type="button" onClick={() => onChange([...items,{quantity:1,unit_price:0,purchase_requisition_item_id:null,is_taxable:false,tax_rate:0}])}>Add Item</Button>}
  </div>;
}

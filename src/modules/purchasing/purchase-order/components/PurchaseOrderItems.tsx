import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import CurrencyInput from "@/components/form/CurrencyInput";

export interface PurchaseOrderItemRow {
  product_id?:number; product_code?:string; product_name?:string; description?:string; uom?:string;
  requested_quantity?:number; remaining_quantity?:number; quantity:number; unit_price:number;
  purchase_requisition_item_id?:number|null;
}
interface ProductOption { id:number; code:string; name:string; description?:string|null; uom:string }
interface Props { items:PurchaseOrderItemRow[]; products:ProductOption[]; fromRequisition:boolean; onChange:(rows:PurchaseOrderItemRow[])=>void }

export default function PurchaseOrderItems({items,products,fromRequisition,onChange}:Props) {
  const update = (index:number, values:Partial<PurchaseOrderItemRow>) => onChange(items.map((row,rowIndex) => rowIndex === index ? {...row,...values} : row));
  const selectProduct = (index:number, productId:number) => {
    const product = products.find((item) => item.id === productId);
    update(index,{product_id:productId || undefined,product_code:product?.code,product_name:product?.name,description:product?.description ?? "",uom:product?.uom ?? ""});
  };

  return <div className="space-y-4">
    <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="table-grid min-w-[900px] w-full text-sm">
      <thead className="bg-slate-50"><tr>{fromRequisition && <th className="p-3 text-left">Item Code</th>}<th className="p-3 text-left">Item Name</th><th className="p-3 text-left">Description</th>{fromRequisition && <th className="p-3 text-right">Requested Qty</th>}{fromRequisition && <th className="p-3 text-right">Remaining Qty</th>}<th className="p-3 text-right">{fromRequisition ? "Selected Qty" : "Quantity"}</th><th className="p-3 text-left">UOM</th><th className="p-3 text-right">Unit Cost</th><th className="p-3 text-right">Line Total</th>{!fromRequisition && <th className="w-24"/>}</tr></thead>
      <tbody>{items.map((row,index) => <tr key={row.purchase_requisition_item_id ?? index} className="border-t">
        {fromRequisition && <td className="p-3">{row.product_code || "—"}</td>}
        <td className="p-2">{fromRequisition ? row.product_name : <select className="h-10 w-full rounded-md border border-slate-300 px-2" value={row.product_id ?? ""} onChange={(event) => selectProduct(index,Number(event.target.value))}><option value="">Select item</option>{products.map((product) => <option key={product.id} value={product.id}>{product.code} - {product.name}</option>)}</select>}</td>
        <td className="p-2">{fromRequisition ? (row.description || "—") : <Input value={row.description ?? ""} onChange={(event) => update(index,{description:event.target.value})}/>}</td>
        {fromRequisition && <td className="p-3 text-right">{row.requested_quantity}</td>}{fromRequisition && <td className="p-3 text-right">{row.remaining_quantity}</td>}
        <td className="p-2"><Input type="number" min="0.01" max={fromRequisition ? row.remaining_quantity : undefined} step="0.01" value={row.quantity} onChange={(event) => update(index,{quantity:Number(event.target.value)})}/></td>
        <td className="p-3">{row.uom || "—"}</td>
        <td className="p-2"><CurrencyInput value={row.unit_price} onValueChange={(value) => update(index,{unit_price:value})}/></td>
        <td className="p-3 text-right font-medium tabular-nums">{(row.quantity * row.unit_price).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
        {!fromRequisition && <td className="p-2"><Button variant="danger" size="sm" onClick={() => onChange(items.filter((_,rowIndex) => rowIndex !== index))}>Remove</Button></td>}
      </tr>)}</tbody>
    </table></div>
    {!fromRequisition && <Button onClick={() => onChange([...items,{quantity:1,unit_price:0,purchase_requisition_item_id:null}])}>Add Item</Button>}
  </div>;
}

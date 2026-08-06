import Button from "@/components/ui/Button";
import CurrencyInput from "@/components/form/CurrencyInput";
import ProductCombobox from "@/components/form/ProductCombobox";
import QuantityInput from "@/components/form/QuantityInput";

export interface Product { id:number; code?:string; product_code?:string; product_name?:string; name?:string }
export interface PurchaseRequisitionItemRow { product_id:number; quantity:number; estimated_price:number }
interface Props { items:PurchaseRequisitionItemRow[]; products:Product[]; loadingProducts?:boolean; onChange:(rows:PurchaseRequisitionItemRow[])=>void }

export default function PurchaseRequisitionItems({items, products, loadingProducts, onChange}:Props) {
  const updateRow = (index:number, field:keyof PurchaseRequisitionItemRow, value:number) => onChange(items.map((row,i) => i === index ? {...row,[field]:value} : row));
  const addRow = () => onChange([...items,{product_id:0,quantity:1,estimated_price:0}]);
  const removeRow = (index:number) => items.length > 1 && onChange(items.filter((_,i) => i !== index));
  const grandTotal = items.reduce((sum,row) => sum + row.quantity * row.estimated_price,0);

  return <div className="space-y-5">
    <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="table-grid min-w-[850px] w-full"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Product</th><th className="w-32 p-3">Qty</th><th className="w-44 p-3">Estimated Price</th><th className="w-44 p-3">Line Total</th><th/></tr></thead>
      <tbody>{items.map((row,index) => <tr key={index} className="border-t">
        <td className="p-2"><ProductCombobox value={row.product_id || undefined} products={products} disabled={loadingProducts} onChange={(productId) => updateRow(index,"product_id",productId)}/></td>
        <td className="p-2"><QuantityInput value={row.quantity} min={0} step={0.01} onValueChange={(value) => updateRow(index,"quantity",value)}/></td>
        <td className="p-2"><CurrencyInput value={row.estimated_price} onValueChange={(value) => updateRow(index,"estimated_price",value)}/></td>
        <td className="pr-3 text-right font-semibold tabular-nums">{(row.quantity * row.estimated_price).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
        <td className="p-2"><Button type="button" variant="danger" size="sm" disabled={items.length === 1} onClick={() => removeRow(index)}>Remove</Button></td>
      </tr>)}</tbody>
    </table></div>
    <div className="flex justify-between"><Button type="button" onClick={addRow}>Add Item</Button><div className="rounded-lg border bg-slate-50 px-6 py-4"><div className="text-sm text-slate-500">Total Estimate</div><div className="text-2xl font-bold tabular-nums">{grandTotal.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div></div>
  </div>;
}

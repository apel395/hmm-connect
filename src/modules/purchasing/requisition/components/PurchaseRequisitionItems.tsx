import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import CurrencyInput from "@/components/form/CurrencyInput";

export interface Product { id:number; product_code?:string; product_name?:string; name?:string }
export interface PurchaseRequisitionItemRow { product_id:number; quantity:number; estimated_price:number }
interface Props { items:PurchaseRequisitionItemRow[]; products:Product[]; loadingProducts?:boolean; onChange:(rows:PurchaseRequisitionItemRow[])=>void }

export default function PurchaseRequisitionItems({items, products, loadingProducts, onChange}:Props) {
  const updateRow = (index:number, field:keyof PurchaseRequisitionItemRow, value:number) => onChange(items.map((row,i) => i === index ? {...row,[field]:value} : row));
  const addRow = () => onChange([...items,{product_id:0,quantity:1,estimated_price:0}]);
  const removeRow = (index:number) => items.length > 1 && onChange(items.filter((_,i) => i !== index));
  const grandTotal = items.reduce((sum,row) => sum + row.quantity * row.estimated_price,0);

  return <div className="space-y-5">
    <table className="table-grid w-full rounded-lg border"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Product</th><th className="w-32 p-3">Qty</th><th className="w-44 p-3">Estimated Price</th><th className="w-44 p-3">Line Total</th><th/></tr></thead>
      <tbody>{items.map((row,index) => <tr key={index}>
        <td className="p-2"><select className="w-full rounded border p-2" disabled={loadingProducts} value={row.product_id} onChange={(event) => updateRow(index,"product_id",Number(event.target.value))}><option value={0}>Select Product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.product_code ? `${product.product_code} - ` : ""}{product.product_name ?? product.name}</option>)}</select></td>
        <td className="p-2"><Input type="number" min={1} value={row.quantity} onChange={(event) => updateRow(index,"quantity",Number(event.target.value))}/></td>
        <td className="p-2"><CurrencyInput value={row.estimated_price} onValueChange={(value) => updateRow(index,"estimated_price",value)}/></td>
        <td className="pr-3 text-right font-semibold tabular-nums">{(row.quantity * row.estimated_price).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
        <td className="p-2"><Button variant="danger" size="sm" disabled={items.length === 1} onClick={() => removeRow(index)}>Remove</Button></td>
      </tr>)}</tbody>
    </table>
    <div className="flex justify-between"><Button onClick={addRow}>Add Item</Button><div className="rounded-lg border bg-slate-50 px-6 py-4"><div className="text-sm text-slate-500">Total Estimate</div><div className="text-2xl font-bold tabular-nums">{grandTotal.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div></div>
  </div>;
}

import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import type { AccountLookup } from "@/modules/master/chart-of-accounts/types";
import { productApi } from "../api/productApi";
import type { Product } from "../types";

interface Props {
  productId: number | null;
  accounts: AccountLookup[];
  onClose: () => void;
  onEdit: (product: Product) => void;
}

const amount = (value: string | number) => Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const quantity = (value: string | number) => Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

export default function ProductDetailDialog({ productId, accounts, onClose, onEdit }: Props) {
  const query = useQuery({
    queryKey: ["product-detail", productId],
    queryFn: async () => (await productApi.detail(productId!)).data,
    enabled: productId !== null,
  });
  const detail = query.data;
  const item = detail?.item;
  const account = (id?: number | null) => {
    const row = accounts.find((entry) => entry.id === id);
    return row ? `${row.account_code} — ${row.account_name}` : id ? `Account #${id}` : "—";
  };
  const primaryAccount = item?.inventory_treatment === "STOCK" ? item.inventory_account_id :
    item?.inventory_treatment === "FIXED_ASSET" ? item.asset_account_id : item?.purchase_account_id;

  return <Dialog open={productId !== null} onOpenChange={(open) => !open && onClose()}>
    <DialogContent className="max-w-5xl">
      <DialogHeader><DialogTitle>{item ? `${item.code} — ${item.name}` : "Item details"}</DialogTitle></DialogHeader>
      <DialogBody>
        {query.isLoading && <p className="text-sm text-slate-500">Loading item details...</p>}
        {query.isError && <p className="text-sm text-red-700">Item details could not be loaded.</p>}
        {item && detail && <div className="space-y-5 text-sm">
          <section className="grid gap-3 rounded-lg border border-slate-200 p-4 md:grid-cols-3">
            <div><div className="text-slate-500">Classification</div><strong>{item.group_name}{item.item_type === "BUY" && item.subgroup_name ? ` / ${item.subgroup_name}` : ""}</strong></div>
            <div><div className="text-slate-500">Department</div><strong>{item.department_name || "Shared"}</strong></div>
            <div><div className="text-slate-500">Product ID</div><strong>{item.id}</strong></div>
            <div><div className="text-slate-500">Treatment</div><strong>{item.inventory_treatment.replace(/_/g, " ")}</strong></div>
            <div><div className="text-slate-500">Purchase → Usage UOM</div><strong>{item.uom} → {quantity(item.conversion)} {item.usage_uom}</strong></div>
            {item.item_type === "BUY" && <div><div className="text-slate-500">Posting account</div><strong>{account(primaryAccount)}</strong></div>}
            {item.inventory_treatment === "STOCK" && <div><div className="text-slate-500">Stock usage expense (OUT)</div><strong>{account(item.cogs_account_id)}</strong></div>}
            <div><div className="text-slate-500">Tax profile</div><strong>{item.tax_category}{item.is_taxable ? ` · ${quantity(item.tax_rate)}%` : ""}</strong></div>
            <div><div className="text-slate-500">Status</div><strong>{item.is_active ? "Active" : "Inactive"}</strong></div>
            {item.description && <p className="md:col-span-3">{item.description}</p>}
          </section>

          {item.item_type === "SELL" && <section className="grid gap-3 rounded-lg border border-blue-200 bg-blue-50/30 p-4 md:grid-cols-3">
            <div><div className="text-slate-500">Service</div><strong>{item.sales_service_name || "—"}</strong></div>
            <div><div className="text-slate-500">Selling price</div><strong>Rp {amount(item.selling_price)}</strong></div>
            <div><div className="text-slate-500">Business unit / Location</div><strong>{detail.sales_scope?.business_unit || "—"} / {detail.sales_scope?.location || "—"}</strong></div>
            <div><div className="text-slate-500">PBJT</div><strong>{quantity(item.pbjt_rate || 0)}%</strong></div>
            <div><div className="text-slate-500">PPN</div><strong>{quantity(item.sales_ppn_rate || 0)}%</strong></div>
            <div><div className="text-slate-500">PPh 23</div><strong>{quantity(item.pph23_rate || 0)}%</strong></div>
          </section>}

          {item.inventory_treatment === "STOCK" && <section>
            <h3 className="mb-2 font-semibold">Stock by warehouse</h3>
            {detail.stock.length === 0 ? <p className="text-slate-500">No stock recorded.</p> :
              <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-left">
                <thead className="bg-slate-50"><tr><th className="p-2">Warehouse</th><th className="p-2 text-right">Quantity</th><th className="p-2 text-right">Average cost</th><th className="p-2 text-right">Value</th></tr></thead>
                <tbody>{detail.stock.map((row) => <tr className="border-t" key={row.warehouse_id}><td className="p-2">{row.warehouse ?? row.warehouse_id}</td><td className="p-2 text-right">{quantity(row.quantity)}</td><td className="p-2 text-right">{amount(row.average_cost)}</td><td className="p-2 text-right">{amount(row.value)}</td></tr>)}</tbody>
              </table></div>}
            <Link className="mt-2 inline-block text-blue-700 hover:underline" to="/inventory/movements" onClick={onClose}>Open stock movement history</Link>
          </section>}

          <section>
            <h3 className="mb-2 font-semibold">Recent purchase prices</h3>
            {detail.purchases.length === 0 ? <p className="text-slate-500">No approved purchase orders yet.</p> :
              <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-left">
                <thead className="bg-slate-50"><tr><th className="p-2">Date / PO</th><th className="p-2">Supplier</th><th className="p-2 text-right">Quantity</th><th className="p-2 text-right">Unit price</th></tr></thead>
                <tbody>{detail.purchases.map((row, index) => <tr className="border-t" key={`${row.order_id}-${index}`}><td className="p-2">{row.order_date}<br/><Link className="text-blue-700 hover:underline" to={`/purchase-orders/${row.order_id}`} onClick={onClose}>{row.po_number}</Link><span className="ml-2 inline-block"><PrintPreviewButton src={`/purchase-orders/${row.order_id}/print`} title={row.po_number}/></span></td><td className="p-2">{row.supplier}</td><td className="p-2 text-right">{quantity(row.quantity)} {row.uom}</td><td className="p-2 text-right">{amount(row.unit_price)}</td></tr>)}</tbody>
              </table></div>}
          </section>

          <section>
            <h3 className="mb-2 font-semibold">Recent receiving</h3>
            {detail.receiving.length === 0 ? <p className="text-slate-500">No posted receipts yet.</p> :
              <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full text-left">
                <thead className="bg-slate-50"><tr><th className="p-2">Date / receipt</th><th className="p-2 text-right">Quantity</th><th className="p-2 text-right">Unit cost</th></tr></thead>
                <tbody>{detail.receiving.map((row, index) => <tr className="border-t" key={`${row.receipt_id}-${index}`}><td className="p-2">{row.received_at.slice(0, 10)}<br/><Link className="text-blue-700 hover:underline" to={`/receiving/${row.receipt_id}`} onClick={onClose}>{row.receipt_number}</Link><span className="ml-2 inline-block"><PrintPreviewButton src={`/receiving/${row.receipt_id}/print`} title={row.receipt_number}/></span></td><td className="p-2 text-right">{quantity(row.quantity)}</td><td className="p-2 text-right">{amount(row.unit_cost)}</td></tr>)}</tbody>
              </table></div>}
          </section>
          {item.inventory_treatment === "FIXED_ASSET" && <p className="rounded-lg bg-blue-50 p-3 text-blue-900">Each physical unit is tracked in the <Link className="font-medium underline" to="/fixed-assets" onClick={onClose}>Fixed Asset register</Link>. The item master and receiving records describe the purchase; depreciation belongs to the asset record.</p>}
        </div>}
      </DialogBody>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Close</Button>
        {item && <Button onClick={() => onEdit(item)}>Edit item</Button>}
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}

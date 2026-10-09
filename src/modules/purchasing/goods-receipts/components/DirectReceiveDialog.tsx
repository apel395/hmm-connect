import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import QuantityInput from "@/components/form/QuantityInput";
import ProductCombobox, {
  type ProductComboboxOption,
} from "@/components/form/ProductCombobox";
import SearchableSelect from "@/components/form/SearchableSelect";
import {
  filterBusinessUnits,
  listDepartments,
  listLocations,
} from "@/modules/admin/organization/api";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import useAuthorization from "@/hooks/useAuthorization";
import { nowLocal } from "@/utils/dateConstraints";
import { useReceiveGoods } from "../hooks/useGoodsReceipts";

type Line = { product_id: number; quantity: number; unit_cost: number; expense_account_id?: number | null };
const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
const option = (row: any) => ({
  id: Number(row.id),
  label: row.code ? `${row.code} - ${row.name}` : row.name,
  keywords: [row.code ?? "", row.name ?? ""],
});
export default function DirectReceiveDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { data: suppliers = [] } = useSuppliers();
  const { data: warehouses = [] } = useWarehouses();
  const receive = useReceiveGoods();
  const { hasPermission } = useAuthorization();
  const [catalogType, setCatalogType] = useState<"CATERING" | "HOTEL">("CATERING");
  const [supplierId, setSupplierId] = useState<number>();
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [destinationType, setDestinationType] = useState<
    "WAREHOUSE" | "DIRECT_USE"
  >("WAREHOUSE");
  const expenseAccounts = useQuery({queryKey:["receiving-expense-accounts"],queryFn:()=>getAllAccountLookup({account_type:"EXPENSE",is_active:true,is_posting:true}),enabled:open && destinationType === "DIRECT_USE"});
  const [warehouseId, setWarehouseId] = useState<number>();
  const [receivedAt, setReceivedAt] = useState(nowLocal());
  const [historical, setHistorical] = useState(false);
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([
    { product_id: 0, quantity: 1, unit_cost: 0 },
  ]);
  const [productRows, setProductRows] = useState<ProductComboboxOption[]>([]);
  const businessUnits = useQuery({
    queryKey: ["business-units", "direct-receipt"],
    queryFn: () => filterBusinessUnits({ is_active: true }),
    enabled: open,
  });
  const departments = useQuery({
    queryKey: ["departments", "direct-receipt", businessUnitId, locationId],
    queryFn: () =>
      listDepartments({ business_unit_id: businessUnitId, location_id: locationId, is_active: true }),
    enabled: open && !!locationId,
  });
  const locations = useQuery({
    queryKey: ["locations", "direct-receipt", businessUnitId],
    queryFn: () =>
      listLocations({ business_unit_id: businessUnitId, is_active: true, assigned_only: true }),
    enabled: open && !!businessUnitId,
  });
  const rememberProduct = (product: ProductComboboxOption) =>
    setProductRows((current) =>
      current.some((row) => row.id === product.id)
        ? current
        : [...current, product],
    );
  const subtotal = useMemo(
    () =>
      lines.reduce(
        (sum, line) =>
          sum + Number(line.quantity || 0) * Number(line.unit_cost || 0),
        0,
      ),
    [lines],
  );
  const tax = useMemo(
    () =>
      lines.reduce((sum, line) => {
        const product = productRows.find((p) => p.id === line.product_id);
        if (!product?.is_taxable) return sum;
        return (
          sum +
          (Number(line.quantity || 0) *
            Number(line.unit_cost || 0) *
            Number(product.tax_rate || 0)) /
            100
        );
      }, 0),
    [lines, productRows],
  );
  const hasTaxReview = lines.some(
    (line) =>
      productRows.find((p) => p.id === line.product_id)?.tax_category ===
      "REVIEW_REQUIRED",
  );
  const patch = (index: number, value: Partial<Line>) =>
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, ...value } : line)),
    );
  const submit = async () => {
    if (!supplierId || !businessUnitId || !departmentId || !locationId)
      return alert(
        "Supplier, Business Unit, Department and Location are required.",
      );
    if (destinationType === "WAREHOUSE" && !warehouseId)
      return alert("Warehouse is required.");
    if (!receivedAt)
      return alert("Receipt Date/Time is required.");
    const items = lines
      .filter((line) => line.product_id && line.quantity > 0)
      .map((line) => ({
        product_id: line.product_id,
        expense_account_id: destinationType === "DIRECT_USE" ? line.expense_account_id ?? null : null,
        quantity: line.quantity,
        unit_cost: line.unit_cost,
      }));
    if (!items.length) return alert("Add at least one valid item.");
    if (destinationType === "DIRECT_USE" && items.some(item => {
      const product=productRows.find(row=>row.id===item.product_id);
      return product?.catalog_type === "HOTEL" && product.inventory_treatment !== "FIXED_ASSET" && !item.expense_account_id;
    })) return alert("Choose an expense destination for each Hotel Direct Use item in the selected department.");
    if (items.some((item) => Number(item.unit_cost) <= 0))
      return alert(
        "Unit cost must be greater than zero for every received item.",
      );
    if (hasTaxReview)
      return alert(
        "One or more items still require Finance tax review in Item Master before this receiving document can continue.",
      );
    try {
      await receive.mutateAsync({
        payload: {
          source_type: historical ? "HISTORICAL_ENTRY" : "LIVE",
          supplier_id: supplierId,
          business_unit_id: businessUnitId,
          department_id: departmentId,
          location_id: locationId,
          received_at: new Date(receivedAt).toISOString(),
          external_reference: reference || null,
          destination_type: destinationType,
          warehouse_id: destinationType === "WAREHOUSE" ? warehouseId : null,
          notes: notes || null,
          items,
        },
      });
      onClose();
    } catch (error) {
      const detail = axios.isAxiosError(error)
        ? error.response?.data?.detail
        : null;
      alert(
        typeof detail === "string"
          ? detail
          : "Direct receipt could not be saved",
      );
    }
  };
  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Create Direct Receiving Draft</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {hasPermission("receiving.post") && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={historical} onChange={event => setHistorical(event.target.checked)}/> Historical entry (Draft → Post)</label>}
          {!historical && <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">
            Use this only when goods/services are received without a Purchase
            Order. Saving creates a <strong>Draft RR</strong>; it must follow
            Store and PM/Camp Boss approval by two different people before posting.
          </div>}
          <div className="grid gap-3 md:grid-cols-2">
            <SearchableSelect
              label="Supplier"
              value={supplierId}
              placeholder="Type supplier code or name..."
              options={(suppliers as any[]).map(option)}
              onChange={setSupplierId}
            />
            <SearchableSelect
              label="Business Unit"
              value={businessUnitId}
              placeholder="Type business unit..."
              options={(businessUnits.data ?? []).map(option)}
              onChange={(id) => {
                setBusinessUnitId(id);
                setDepartmentId(undefined);
                setLocationId(undefined);
              }}
            />
            <SearchableSelect
              label="Department"
              disabled={!locationId || departments.isLoading}
              value={departmentId}
              placeholder="Type department..."
              options={(departments.data ?? []).map(option)}
              onChange={setDepartmentId}
            />
            <SearchableSelect
              label="Location"
              value={locationId}
              placeholder="Type location..."
              options={(locations.data ?? []).map(option)}
              onChange={id=>{setLocationId(id);setDepartmentId(undefined);setWarehouseId(undefined)}}
            />
            <label className="text-xs font-medium text-slate-700">
              Receipt Date
              <input
                type="datetime-local"
                data-accounting-date="true"
                data-min-date="2026-01-01"
                min="2026-01-01T00:00"
                className="mt-1 h-9 w-full rounded-md border px-3 text-[13px]"
                value={receivedAt}
                onChange={(e) => setReceivedAt(e.target.value)}
              />
            </label>
            <label className="text-xs font-medium text-slate-700">
              Delivery Note / Reference
              <input
                className="mt-1 h-9 w-full rounded-md border px-3 text-[13px]"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
              />
            </label>
            <label className="text-xs font-medium text-slate-700">
              Destination
              <select
                className="mt-1 h-9 w-full rounded-md border px-3 text-[13px]"
                value={destinationType}
                onChange={(e) => setDestinationType(e.target.value as any)}
              >
                <option value="WAREHOUSE">Warehouse</option>
                <option value="DIRECT_USE">Direct Use</option>
              </select>
            </label>
            {destinationType === "WAREHOUSE" && (
              <SearchableSelect
                label="Warehouse"
                value={warehouseId}
                placeholder="Type warehouse code or name..."
                options={(warehouses as any[]).map(option)}
                onChange={setWarehouseId}
              />
            )}
          </div>
          {hasTaxReview && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-800">
              Tax review required: Finance must classify all selected items in
              Item Master before this RR can proceed.
            </div>
          )}
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <label className="mb-2 block text-xs">Item catalog<select className="ml-2 rounded border p-2" value={catalogType} onChange={e=>setCatalogType(e.target.value as "CATERING"|"HOTEL")}><option value="CATERING">Catering Items</option><option value="HOTEL">Hotel Items</option></select></label>
            <table className="min-w-[940px] w-full text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="p-2 text-left">Product</th>
                  <th>UOM</th>
                  <th>Qty</th>
                  <th>Unit Cost</th>
                  <th>Tax</th>
                  <th>PPN</th>
                  <th>Line Total</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => {
                  const product = productRows.find(
                    (p) => p.id === line.product_id,
                  );
                  const base = line.quantity * line.unit_cost;
                  const lineTax = product?.is_taxable
                    ? (base * Number(product.tax_rate || 0)) / 100
                    : 0;
                  return (
                    <tr key={index} className="border-t">
                      <td className="p-2">
                        <ProductCombobox
                          catalogType={catalogType}
                          products={productRows}
                          remote
                          value={line.product_id || undefined}
                          onChange={(id) =>
                            patch(index, { product_id: id || 0 })
                          }
                          onSelect={product => { rememberProduct(product); patch(index, {product_id:product.id, unit_cost:Number(product.reference_cost ?? product.last_purchase_price ?? 0)}); }}
                        />
                        {product?.tax_category === "REVIEW_REQUIRED" && (
                          <div className="mt-1 text-xs font-medium text-red-700">
                            Finance tax review required
                          </div>
                        )}
                      </td>
                      <td>{product?.uom ?? "—"}</td>
                      <td className="p-2">
                        <QuantityInput
                          value={line.quantity}
                          onValueChange={(value) =>
                            patch(index, { quantity: value })
                          }
                        />
                      </td>
                      <td className="p-2">
                        <CurrencyInput
                          value={line.unit_cost}
                          onValueChange={(value) =>
                            patch(index, { unit_cost: value })
                          }
                        />
                        {destinationType === "DIRECT_USE" && <label className="block text-xs">Expense destination<select aria-label="Department expense destination" className="w-full rounded border p-1" value={line.expense_account_id ?? ""} onChange={e=>patch(index,{expense_account_id:Number(e.target.value)||null})}><option value="">{catalogType === "HOTEL" ? "Choose department expense" : "Item expense mapping"}</option>{expenseAccounts.data?.map(account=><option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select></label>}
                      </td>
                      <td>
                        {product?.is_taxable
                          ? `PPN ${Number(product.tax_rate || 0)}%`
                          : (product?.tax_category ?? "—")}
                      </td>
                      <td className="text-right">{money(lineTax)}</td>
                      <td className="text-right font-medium">
                        {money(base + lineTax)}
                      </td>
                      <td className="p-2">
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() =>
                            setLines((current) =>
                              current.filter((_, i) => i !== index),
                            )
                          }
                        >
                          Remove
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex items-start justify-between">
            <Button
              variant="outline"
              onClick={() =>
                setLines((current) => [
                  ...current,
                  { product_id: 0, quantity: 1, unit_cost: 0 },
                ])
              }
            >
              Add Item
            </Button>
            <div className="min-w-64 space-y-1 text-right text-xs tabular-nums">
              <div className="flex justify-between gap-8">
                <span>Subtotal</span>
                <strong>{money(subtotal)}</strong>
              </div>
              <div className="flex justify-between gap-8">
                <span>PPN</span>
                <strong>{money(tax)}</strong>
              </div>
              <div className="flex justify-between gap-8 border-t pt-2 text-sm">
                <span>Grand Total</span>
                <strong>{money(subtotal + tax)}</strong>
              </div>
            </div>
          </div>
          <label className="block text-xs font-medium text-slate-700">
            Notes
            <textarea
              className="mt-1 min-h-20 w-full rounded-md border p-2 text-[13px]"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={receive.isPending} onClick={submit}>
            Save RR Draft
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

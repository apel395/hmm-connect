import { Trash2 } from "lucide-react";
import "../receiving-lines.css";
import api from "@/api/client";
import { useEffect, useMemo, useState } from "react";
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
import ReceivingDestinationField from "./ReceivingDestinationField";
import ReceivingBillingFields from "./ReceivingBillingFields";
import { emptyReceivingBilling, receivingBillingPayload, validateReceivingBilling } from "../billing";
import { destinationFor, destinationError, type LineRouting } from "../destination";

type Line = LineRouting & { market_list_item_id?: number; product_id: number; quantity: number; unit_cost: number; tax_rate?:number; expense_account_id?: number | null };
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
  marketListMode = false,
}: {
  open: boolean;
  onClose: () => void;
  marketListMode?: boolean;
}) {
  const supplierQuery = useSuppliers("", 100, open);
  const suppliers = supplierQuery.data ?? [];
  const { data: warehouses = [] } = useWarehouses();
  const receive = useReceiveGoods();
  const { hasPermission } = useAuthorization();
  const [marketListId, setMarketListId] = useState<number>();
  const marketLists = useQuery({queryKey:["receivable-market-lists"],queryFn:async()=>(await api.get("/goods-receipts/receivable-market-lists")).data,enabled:open && marketListMode,refetchOnWindowFocus:false});
  const [catalogType, setCatalogType] = useState<"CATERING" | "HOTEL" | "ALL">("ALL");
  const [supplierId, setSupplierId] = useState<number>();
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [warehouseId, setWarehouseId] = useState<number>();
  const [receivedAt, setReceivedAt] = useState(nowLocal());
  const [historical, setHistorical] = useState(false);
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [billing, setBilling] = useState(emptyReceivingBilling);
  const [lines, setLines] = useState<Line[]>([
    { product_id: 0, quantity: 1, unit_cost: 0 },
  ]);
  const [productRows, setProductRows] = useState<ProductComboboxOption[]>([]);
  const routingFor = (line: Line) => ({...line, inventory_treatment: productRows.find(product => product.id === line.product_id)?.inventory_treatment});
  const hasWarehouse = lines.some(line => line.product_id && line.quantity > 0 && destinationFor(routingFor(line)) === "WAREHOUSE");
  const hasDirectUse = lines.some(line => line.product_id && destinationFor(routingFor(line)) === "DIRECT_USE");
  const expenseAccounts = useQuery({queryKey:["receiving-expense-accounts"],queryFn:()=>getAllAccountLookup({account_type:"EXPENSE",is_active:true,is_posting:true}),enabled:open && hasDirectUse});
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
  useEffect(() => {
    if (!marketListMode || !marketListId) return;
    const source = (marketLists.data ?? []).find((row: any) => row.id === marketListId);
    if (!source) return;
    setBusinessUnitId(source.business_unit_id);
    setLocationId(source.location_id);
    setDepartmentId(source.department_id);
    setLines(source.items.map((item: any) => ({market_list_item_id:item.market_list_item_id,product_id:item.product_id,quantity:Number(item.remaining_quantity),unit_cost:Number(item.unit_cost),expense_account_id:item.purchase_account_id,tax_rate:item.is_taxable?Number(item.tax_rate??0):0,destination_type:null})));
    setProductRows(source.items.map((item: any) => ({id:item.product_id,code:item.product_code,name:item.product_name,uom:item.uom,catalog_type:item.catalog_type,inventory_treatment:item.inventory_treatment,purchase_account_id:item.purchase_account_id,is_taxable:item.is_taxable,tax_rate:item.tax_rate})));
    setWarehouseId(undefined);
  }, [marketListMode, marketListId, marketLists.data]);
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
  const tax = useMemo(()=>lines.reduce((sum,line)=>sum+line.quantity*line.unit_cost*Number(line.tax_rate||0)/100,0),[lines]);
  const patch = (index: number, value: Partial<Line>) =>
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, ...value } : line)),
    );
  const submit = async () => {
    if (marketListMode && !marketListId) return alert("Choose an approved Market List");
    if (!supplierId || !businessUnitId || !departmentId || !locationId)
      return alert(
        "Supplier, Business Unit, Department and Location are required.",
      );
    if (hasWarehouse && !warehouseId)
      return alert("Warehouse is required.");
    if (!receivedAt)
      return alert("Receipt Date/Time is required.");
    const billingIssue = validateReceivingBilling(billing, subtotal);
    if (billingIssue) return alert(billingIssue);
    const routingIssue = lines.filter(line => line.product_id && line.quantity > 0).map(line => destinationError(routingFor(line))).find(Boolean);
    if (routingIssue) return alert(routingIssue);
    const items = lines
      .filter((line) => line.product_id && line.quantity > 0)
      .map((line) => ({
        market_list_item_id: line.market_list_item_id,
        product_id: line.product_id,
        destination_type: line.destination_type ?? null,
        destination_override_reason: line.destination_override_reason || null,
        expense_account_id: destinationFor(routingFor(line)) === "DIRECT_USE" ? line.expense_account_id ?? null : null,
        quantity: line.quantity,
        unit_cost: line.unit_cost,
        is_taxable: Number(line.tax_rate||0)>0,
        tax_rate: Number(line.tax_rate||0),
      }));
    if (!items.length) return alert("Add at least one valid item.");
    if (items.some(item => {
      const product=productRows.find(row=>row.id===item.product_id);
      return destinationFor({...item, inventory_treatment: product?.inventory_treatment}) === "DIRECT_USE" && product?.catalog_type === "HOTEL" && product.inventory_treatment !== "FIXED_ASSET" && !item.expense_account_id;
    })) return alert("Choose an expense destination for each Hotel Direct Use item in the selected department.");
    if (items.some((item) => Number(item.unit_cost) <= 0))
      return alert(
        "Unit cost must be greater than zero for every received item.",
      );
    try {
      await receive.mutateAsync({
        payload: {
          source_type: historical ? "HISTORICAL_ENTRY" : "LIVE",
          market_list_id: marketListMode ? marketListId : undefined,
          supplier_id: supplierId,
          business_unit_id: businessUnitId,
          department_id: departmentId,
          location_id: locationId,
          received_at: new Date(receivedAt).toISOString(),
          external_reference: reference || null,
          warehouse_id: hasWarehouse ? warehouseId : null,
          notes: notes || null,
          ...receivingBillingPayload(billing),
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
      <DialogContent className="max-w-[1440px]">
        <DialogHeader>
          <DialogTitle>{marketListMode ? "Receiving from Market List" : "Create Direct Receiving Draft"}</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {hasPermission("receiving.post") && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={historical} onChange={event => setHistorical(event.target.checked)}/> Historical entry (Draft → Post)</label>}
          {!historical && <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">
            Use this only when goods/services are received without a Purchase
            Order. Saving creates a <strong>Draft RR</strong>; it must follow
            Store and PM/Camp Boss approval by two different people before posting.
          </div>}
          {marketListMode && <SearchableSelect label="Approved Market List" value={marketListId} options={(marketLists.data ?? []).map((row: any)=>({id:row.id,label:`${row.ml_number} · ${row.request_date}`}))} onChange={setMarketListId} />}
          {supplierQuery.isError && <p role="alert" className="text-sm text-red-700">Suppliers could not load. <button type="button" className="underline" onClick={() => void supplierQuery.refetch()}>Retry</button></p>}
          <div className="grid gap-3 md:grid-cols-2">
            <SearchableSelect
              label="Supplier"
              value={supplierId}
              disabled={supplierQuery.isLoading}
              placeholder={supplierQuery.isLoading ? "Loading suppliers…" : "Type supplier code or name..."}
              options={(suppliers as any[]).map(option)}
              onChange={setSupplierId}
            />
            <SearchableSelect
              label="Business Unit"
              disabled={marketListMode}
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
              disabled={marketListMode || !locationId || departments.isLoading}
              value={departmentId}
              placeholder="Type department..."
              options={(departments.data ?? []).map(option)}
              onChange={setDepartmentId}
            />
            <SearchableSelect
              label="Location"
              disabled={marketListMode}
              value={locationId}
              placeholder="Type location..."
              options={(locations.data ?? []).map(option)}
              onChange={id=>{setLocationId(id);setDepartmentId(undefined);setWarehouseId(undefined)}}
            />
            <label className="text-xs font-medium text-slate-700">
              Receipt Date
              <input
                type="datetime-local" disabled={!historical}
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
            {hasWarehouse && (
              <SearchableSelect
                label="Warehouse"
                value={warehouseId}
                placeholder="Type warehouse code or name..."
                options={(warehouses as any[]).filter(row => row.is_active && Number(row.location_id) === locationId).map(option)}
                onChange={setWarehouseId}
              />
            )}
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <label className="mb-2 block text-xs">Item catalog<select className="ml-2 rounded border p-2" value={catalogType} onChange={e=>setCatalogType(e.target.value as "CATERING"|"HOTEL"|"ALL")}><option value="ALL">All Buy Items</option><option value="CATERING">Catering Items</option><option value="HOTEL">Hotel Items</option></select></label>
            <table className="receiving-lines receiving-lines-direct">
              <colgroup><col/><col className="rl-destination"/><col className="rl-unit"/><col className="rl-quantity"/><col className="rl-cost"/><col className="rl-tax-rate"/><col className="rl-amount"/><col className="rl-total"/><col className="rl-action"/></colgroup>
              <thead className="bg-slate-50">
                <tr>
                  <th className="p-2 text-left">Product</th>
                  <th className="p-2 text-left">Destination</th>
                  <th>UOM</th>
                  <th>Qty</th>
                  <th className="whitespace-nowrap">Unit Cost</th>
                  <th title="Provisional PPN rate; confirmed in AP">PPN %</th>
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
                  const lineTax = base * Number(line.tax_rate||0)/100;
                  return (
                    <tr key={index} className="border-t">
                      <td className="p-2">
                        <ProductCombobox
                          disabled={marketListMode}
                          catalogType={catalogType === "ALL" ? undefined : catalogType}
                          products={productRows}
                          remote={!marketListMode}
                          value={line.product_id || undefined}
                          onChange={(id) =>
                            patch(index, { product_id: id || 0 })
                          }
                          onSelect={product => { rememberProduct(product); patch(index, {product_id:product.id, destination_type:null, destination_override_reason:null, expense_account_id:product.purchase_account_id ?? null, unit_cost:Number(product.reference_cost ?? product.last_purchase_price ?? 0),tax_rate:product.is_taxable?Number(product.tax_rate??0):0}); }}
                        />

                      </td>
                      <td className="p-2"><ReceivingDestinationField name={product?.name ?? `item ${index+1}`} line={routingFor(line)} onChange={value => patch(index, value)}/></td>
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
                        {destinationFor(routingFor(line)) === "DIRECT_USE" && product?.inventory_treatment !== "FIXED_ASSET" && <label className="block text-xs">Expense destination<select aria-label="Department expense destination" className="w-full rounded border p-1" value={line.expense_account_id ?? ""} onChange={e=>patch(index,{expense_account_id:Number(e.target.value)||null})}><option value="">{catalogType === "HOTEL" ? "Choose department expense" : "Item expense mapping"}</option>{expenseAccounts.data?.map(account=><option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select></label>}
                      </td>
                      <td>
                        <input aria-label={`PPN rate for item ${index+1}`} type="number" min="0" max="100" step="0.01" className="h-8 w-20 rounded border px-2 text-right" value={line.tax_rate??0} onChange={event=>patch(index,{tax_rate:Number(event.target.value)})}/>

                      </td>
                      <td className="text-right">{money(lineTax)}</td>
                      <td className="text-right font-medium">
                        {money(base + lineTax)}
                      </td>
                      <td className="p-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Remove item ${index + 1}`}
                          title="Remove item"
                          onClick={() =>
                            setLines((current) =>
                              current.filter((_, i) => i !== index),
                            )
                          }
                        >
                          <Trash2 size={14}/>
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
              disabled={marketListMode}
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
          <ReceivingBillingFields value={billing} onChange={setBilling} subtotal={subtotal} tax={tax} open={open}/>
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



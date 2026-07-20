import { useMemo, useState } from "react";
import { Plus, Printer, Search } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  approvePurchaseOrder,
  createPurchaseOrder,
  getPurchaseOrders,
  receiveGoods,
  rejectPurchaseOrder,
  submitPurchaseOrder,
  type PurchaseOrder,
} from "../features/purchase-orders/purchaseOrdersApi";
import { getProducts, type Product } from "../features/products/productsApi";
import { getSuppliers, type Supplier } from "../features/suppliers/suppliersApi";
import { getPurchaseRequisitions, type PurchaseRequisition } from "../features/purchase-requisitions/purchaseRequisitionsApi";
import { getWarehouses } from "../features/warehouses/warehousesApi";

interface PurchaseOrderLine {
  line_id: string;
  product_id: number;
  quantity: number;
  unit_price: number;
  purchase_requisition_item_id?: number;
}

export default function PurchaseOrdersPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [tolerance, setTolerance] = useState("0");
  const [notes, setNotes] = useState("");
  const [selectedRequisitionIds, setSelectedRequisitionIds] = useState<number[]>([]);
  const [lines, setLines] = useState<PurchaseOrderLine[]>([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [prSearch, setPrSearch] = useState("");

  const [receivingOrder, setReceivingOrder] = useState<PurchaseOrder | null>(null);
  const [receivedQuantities, setReceivedQuantities] = useState<Record<number, string>>({});
  const [destinationType, setDestinationType] = useState<"INVENTORY" | "DIRECT_CONSUMPTION">("INVENTORY");
  const [warehouseId, setWarehouseId] = useState("");

  const productsQuery = useQuery({ queryKey: ["products"], queryFn: getProducts });
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: getSuppliers });
  const requisitionsQuery = useQuery({ queryKey: ["purchase-requisitions"], queryFn: getPurchaseRequisitions });
  const warehousesQuery = useQuery({ queryKey: ["warehouses"], queryFn: getWarehouses });
  const purchaseOrdersQuery = useQuery({ queryKey: ["purchase-orders"], queryFn: getPurchaseOrders });

  const createMutation = useMutation({
    mutationFn: createPurchaseOrder,
    onSuccess: () => {
      resetCreateForm();
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const submitMutation = useMutation({
    mutationFn: submitPurchaseOrder,
    onSuccess: invalidateWorkflow,
  });

  const approveMutation = useMutation({
    mutationFn: approvePurchaseOrder,
    onSuccess: invalidateWorkflow,
  });

  const rejectMutation = useMutation({
    mutationFn: rejectPurchaseOrder,
    onSuccess: invalidateWorkflow,
  });

  function invalidateWorkflow() {
    queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
    queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
  }

  const receiveMutation = useMutation({
    mutationFn: ({ purchaseOrderId, data }: { purchaseOrderId: number; data: { destination_type: "INVENTORY" | "DIRECT_CONSUMPTION"; warehouse_id?: number; items: { purchase_order_item_id: number; quantity: number }[] } }) => receiveGoods(purchaseOrderId, data),
    onSuccess: () => {
      setReceivingOrder(null);
      setReceivedQuantities({});
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const products = productsQuery.data ?? [];
  const suppliers = suppliersQuery.data ?? [];
  const warehouses = warehousesQuery.data ?? [];
  const purchaseOrders = purchaseOrdersQuery.data ?? [];

  const availableRequisitions = useMemo(() => {
    const normalized = prSearch.trim().toLowerCase();
    return (requisitionsQuery.data ?? [])
      .filter((pr) => pr.status === "APPROVED" || pr.status === "CONVERTED")
      .filter((pr) => !normalized || pr.pr_number.toLowerCase().includes(normalized));
  }, [prSearch, requisitionsQuery.data]);

  const totalAmount = useMemo(
    () => lines.reduce((total, line) => total + line.quantity * line.unit_price, 0),
    [lines],
  );

  function resetCreateForm() {
    setCreateOpen(false);
    setSupplierId("");
    setExpectedDate("");
    setExpiryDate("");
    setTolerance("0");
    setNotes("");
    setSelectedRequisitionIds([]);
    setLines([]);
    setSelectedProductId("");
    setQuantity("");
    setUnitPrice("");
    setPrSearch("");
    createMutation.reset();
  }

  function getProduct(productId: number): Product | undefined {
    return products.find((product) => product.id === productId);
  }

  function getSupplier(supplierIdValue: number): Supplier | undefined {
    return suppliers.find((supplier) => supplier.id === supplierIdValue);
  }

  function toggleRequisition(requisition: PurchaseRequisition) {
    const selected = selectedRequisitionIds.includes(requisition.id);

    if (selected) {
      setSelectedRequisitionIds((current) => current.filter((id) => id !== requisition.id));
      setLines((current) => current.filter((line) => !requisition.items.some((item) => item.id === line.purchase_requisition_item_id)));
      return;
    }

    setSelectedRequisitionIds((current) => [...current, requisition.id]);
    setLines((current) => [
      ...current,
      ...requisition.items
        .filter((item) => !current.some((line) => line.purchase_requisition_item_id === item.id))
        .map((item) => ({
          line_id: `pr-${item.id}`,
          product_id: item.product_id,
          quantity: Number(item.quantity),
          unit_price: Number(item.estimated_price),
          purchase_requisition_item_id: item.id,
        })),
    ]);
  }

  function addManualLine() {
    const productId = Number(selectedProductId);
    const lineQuantity = Number(quantity);
    const price = Number(unitPrice);

    if (!productId || lineQuantity <= 0 || price < 0) return;

    const existingLine = lines.find((line) => line.product_id === productId && line.purchase_requisition_item_id === undefined);

    if (existingLine) {
      setLines((current) => current.map((line) => line.line_id === existingLine.line_id ? { ...line, quantity: line.quantity + lineQuantity } : line));
    } else {
      setLines((current) => [...current, { line_id: `manual-${productId}-${Date.now()}`, product_id: productId, quantity: lineQuantity, unit_price: price }]);
    }

    setSelectedProductId("");
    setQuantity("");
    setUnitPrice("");
  }

  function removeLine(lineId: string) {
    setLines((current) => current.filter((line) => line.line_id !== lineId));
  }

  function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supplierId || lines.length === 0) return;

    createMutation.mutate({
      supplier_id: Number(supplierId),
      purchase_requisition_ids: selectedRequisitionIds,
      expected_date: expectedDate || undefined,
      expiry_date: expiryDate || undefined,
      receipt_tolerance_percent: Number(tolerance || 0),
      notes: notes || undefined,
      items: lines.map((line) => ({
        product_id: line.product_id,
        quantity: line.quantity,
        unit_price: line.unit_price,
        purchase_requisition_item_id: line.purchase_requisition_item_id,
      })),
    });
  }

  function openReceiveModal(order: PurchaseOrder) {
    setReceivingOrder(order);
    setDestinationType("INVENTORY");
    setWarehouseId("");
    setReceivedQuantities(Object.fromEntries(order.items.map((item) => [item.id, ""])));
  }

  function closeReceiveModal() {
    if (receiveMutation.isPending) return;
    setReceivingOrder(null);
    setReceivedQuantities({});
  }

  function handleReceive() {
    if (!receivingOrder) return;

    const items = receivingOrder.items
      .map((item) => ({ purchase_order_item_id: item.id, quantity: Number(receivedQuantities[item.id] || 0) }))
      .filter((item) => item.quantity > 0);

    if (items.length === 0) return;

    receiveMutation.mutate({
      purchaseOrderId: receivingOrder.id,
      data: {
        destination_type: destinationType,
        warehouse_id: destinationType === "INVENTORY" ? Number(warehouseId) : undefined,
        items,
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchase Orders"
        description="Create POs from approved PRs and receive goods with controlled tolerance."
        actions={
          <>
            <Button type="button" variant="secondary" onClick={() => window.print()}>
              <Printer size={16} className="mr-2" />
              Print
            </Button>
            <Button type="button" onClick={() => { createMutation.reset(); setCreateOpen(true); }}>
              <Plus size={16} className="mr-2" />
              Create PO
            </Button>
          </>
        }
      />

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-slate-900">Purchase orders</h2>
            <p className="mt-1 text-sm text-slate-500">{purchaseOrders.length} purchase orders</p>
          </div>
        </div>

        {purchaseOrdersQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading purchase orders...</div>}
        {purchaseOrdersQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load purchase orders.</div>}

        {!purchaseOrdersQuery.isLoading && !purchaseOrdersQuery.isError && purchaseOrders.length === 0 && (
          <EmptyState title="No purchase orders yet" description="Create a PO from one or more approved purchase requisitions." action={<Button type="button" onClick={() => setCreateOpen(true)}><Plus size={16} className="mr-2" />Create PO</Button>} />
        )}

        {purchaseOrders.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">PO Number</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Supplier</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Expiry</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Total</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Action</th>
                </tr>
              </thead>
              <tbody>
                {purchaseOrders.map((order) => {
                  const supplier = getSupplier(order.supplier_id);
                  return (
                    <tr key={order.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                      <td className="px-6 py-4 text-sm font-medium text-slate-900">{order.po_number}</td>
                      <td className="px-6 py-4 text-sm text-slate-600">{supplier?.name ?? "Supplier"}</td>
                      <td className="px-6 py-4"><StatusBadge status={order.status} /></td>
                      <td className="px-6 py-4 text-sm text-slate-600">{order.expiry_date ?? "—"}</td>
                      <td className="px-6 py-4 text-right text-sm font-medium text-slate-900">{Number(order.total_amount).toFixed(2)}</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-2">
                          {order.status === "DRAFT" && <Button type="button" onClick={() => submitMutation.mutate(order.id)} loading={submitMutation.isPending}>Submit</Button>}
                          {order.status === "PENDING_APPROVAL" && <>
                            <Button type="button" onClick={() => approveMutation.mutate(order.id)} loading={approveMutation.isPending}>Approve</Button>
                            <Button type="button" variant="danger" onClick={() => rejectMutation.mutate(order.id)} loading={rejectMutation.isPending}>Reject</Button>
                          </>}
                          <Button type="button" variant="secondary" onClick={() => openReceiveModal(order)} disabled={order.status !== "APPROVED" && order.status !== "RECEIVING"}>
                            Receive
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={createOpen}
        onClose={resetCreateForm}
        title="Create purchase order"
        description="Select one or more approved PRs, then review the PO before creating it."
        size="xl"
        closeDisabled={createMutation.isPending}
        footer={
          <>
            <Button type="button" variant="secondary" onClick={resetCreateForm} disabled={createMutation.isPending}>Cancel</Button>
            <Button type="submit" form="create-po-form" loading={createMutation.isPending} disabled={!supplierId || lines.length === 0}>Create purchase order</Button>
          </>
        }
      >
        <form id="create-po-form" onSubmit={handleCreate} className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Supplier</label>
              <Select value={supplierId} onChange={setSupplierId} placeholder="Select supplier" options={suppliers.map((supplier) => ({ value: String(supplier.id), label: `${supplier.code} - ${supplier.name}` }))} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Receipt tolerance (%)</label>
              <input type="number" min="0" max="100" step="0.01" value={tolerance} onChange={(event) => setTolerance(event.target.value)} className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Expected date</label>
              <input type="date" value={expectedDate} onChange={(event) => setExpectedDate(event.target.value)} className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">PO expiry date</label>
              <input type="date" value={expiryDate} onChange={(event) => setExpiryDate(event.target.value)} className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
            </div>
          </div>

          <section className="rounded-xl border border-slate-200">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Approved PRs</h3>
                <p className="mt-1 text-xs text-slate-500">Select multiple PRs to combine into one PO.</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">{selectedRequisitionIds.length} selected</span>
                <div className="flex h-9 w-52 items-center gap-2 rounded-lg bg-slate-50 px-2.5">
                  <Search size={15} className="text-slate-400" />
                  <input value={prSearch} onChange={(event) => setPrSearch(event.target.value)} placeholder="Search PR..." className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400" />
                </div>
              </div>
            </div>
            <div className="max-h-56 overflow-y-auto p-3">
              {availableRequisitions.length === 0 ? <p className="p-3 text-sm text-slate-500">No approved PRs available.</p> : availableRequisitions.map((requisition) => {
                const selected = selectedRequisitionIds.includes(requisition.id);
                return (
                  <button key={requisition.id} type="button" onClick={() => toggleRequisition(requisition)} className={`flex w-full items-center justify-between rounded-lg px-3 py-3 text-left transition ${selected ? "bg-slate-900 text-white" : "hover:bg-slate-50"}`}>
                    <span className="flex items-center gap-3">
                      <span className={`flex h-5 w-5 items-center justify-center rounded border text-xs ${selected ? "border-white bg-white text-slate-900" : "border-slate-300"}`}>{selected ? "✓" : ""}</span>
                      <span>
                        <span className="block text-sm font-medium">{requisition.pr_number}</span>
                        <span className={`block text-xs ${selected ? "text-slate-300" : "text-slate-500"}`}>{requisition.request_date} · {requisition.items.length} items</span>
                      </span>
                    </span>
                    <span className={`text-sm font-medium ${selected ? "text-white" : "text-slate-700"}`}>{Number(requisition.total_amount).toFixed(2)}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-900">Add manual item</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-[1fr_140px_140px_auto]">
              <Select value={selectedProductId} onChange={setSelectedProductId} placeholder="Select product" options={products.map((product) => ({ value: String(product.id), label: `${product.code} - ${product.name}` }))} />
              <input type="number" min="0.01" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="Quantity" className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
              <input type="number" min="0" step="0.01" value={unitPrice} onChange={(event) => setUnitPrice(event.target.value)} placeholder="Unit price" className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
              <Button type="button" variant="secondary" onClick={addManualLine}>Add</Button>
            </div>
          </section>

          {lines.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-900">PO items</h3>
              {lines.map((line) => {
                const product = getProduct(line.product_id);
                return (
                  <div key={line.line_id} className="flex items-center justify-between rounded-lg bg-slate-50 p-3">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{product?.name ?? "Product"}</p>
                      <p className="text-xs text-slate-500">{line.quantity} {product?.uom ?? ""} × {line.unit_price}{line.purchase_requisition_item_id ? " · PR sourced" : " · Direct"}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-slate-900">{(line.quantity * line.unit_price).toFixed(2)}</span>
                      <button type="button" onClick={() => removeLine(line.line_id)} className="text-xs font-medium text-red-600 hover:text-red-700">Remove</button>
                    </div>
                  </div>
                );
              })}
              <div className="flex items-center justify-between border-t border-slate-200 pt-4">
                <span className="text-sm font-medium text-slate-600">Total</span>
                <span className="text-xl font-semibold text-slate-900">{totalAmount.toFixed(2)}</span>
              </div>
            </section>
          )}

          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} placeholder="Notes (optional)" className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
          {createMutation.isError && <p className="text-sm text-red-600">Failed to create purchase order.</p>}
        </form>
      </Modal>

      <Modal
        open={Boolean(receivingOrder)}
        onClose={closeReceiveModal}
        title="Receive goods"
        description={receivingOrder ? `${receivingOrder.po_number} · receipt tolerance ${receivingOrder.receipt_tolerance_percent}%` : undefined}
        size="lg"
        closeDisabled={receiveMutation.isPending}
        footer={
          <>
            <Button type="button" variant="secondary" onClick={closeReceiveModal} disabled={receiveMutation.isPending}>Cancel</Button>
            <Button type="button" onClick={handleReceive} loading={receiveMutation.isPending} disabled={destinationType === "INVENTORY" && !warehouseId}>Receive goods</Button>
          </>
        }
      >
        {receivingOrder && (
          <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Destination</label>
                <Select value={destinationType} onChange={(value) => setDestinationType(value as "INVENTORY" | "DIRECT_CONSUMPTION")} options={[{ value: "INVENTORY", label: "Inventory" }, { value: "DIRECT_CONSUMPTION", label: "Direct consumption" }]} />
              </div>
              {destinationType === "INVENTORY" && (
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">Warehouse</label>
                  <Select value={warehouseId} onChange={setWarehouseId} placeholder="Select warehouse" options={warehouses.map((warehouse) => ({ value: String(warehouse.id), label: `${warehouse.code} - ${warehouse.name}` }))} />
                </div>
              )}
            </div>

            <div className="space-y-2">
              {receivingOrder.items.map((item) => {
                const product = getProduct(item.product_id);
                const allowed = Number(item.quantity) * (1 + Number(receivingOrder.receipt_tolerance_percent) / 100);
                const remaining = Math.max(0, allowed - Number(item.received_quantity));
                return (
                  <div key={item.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-sm font-medium text-slate-900">{product?.name ?? "Product"}</p>
                        <p className="mt-1 text-xs text-slate-500">Allowed remaining: {remaining.toFixed(2)} {product?.uom ?? ""}</p>
                      </div>
                      <input type="number" min="0" max={remaining} step="0.01" value={receivedQuantities[item.id] ?? ""} onChange={(event) => setReceivedQuantities((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Qty" className="h-10 w-28 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
                    </div>
                  </div>
                );
              })}
            </div>
            {receiveMutation.isError && <p className="text-sm text-red-600">Failed to receive goods.</p>}
          </div>
        )}
      </Modal>
    </div>
  );
}

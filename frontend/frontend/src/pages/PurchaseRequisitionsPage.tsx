import { useMemo, useState } from "react";
import { Plus, Printer } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";
import { StatusBadge } from "../components/ui/StatusBadge";
import {
  approvePurchaseRequisition,
  createPurchaseRequisition,
  getPurchaseRequisition,
  getPurchaseRequisitionTraceability,
  getPurchaseRequisitions,
  rejectPurchaseRequisition,
  submitPurchaseRequisition,
  type PurchaseRequisition,
} from "../features/purchase-requisitions/purchaseRequisitionsApi";
import { getProducts, type Product } from "../features/products/productsApi";
import { getApprovalStatus } from "../features/approval-workflows/approvalWorkflowsApi";

interface PurchaseLine {
  product_id: number;
  quantity: number;
  estimated_price: number;
}

export default function PurchaseRequisitionsPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<PurchaseLine[]>([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [estimatedPrice, setEstimatedPrice] = useState("");
  const [selectedRequisitionId, setSelectedRequisitionId] = useState<number | null>(null);

  const productsQuery = useQuery<Product[]>({ queryKey: ["products"], queryFn: getProducts });
  const requisitionsQuery = useQuery<PurchaseRequisition[]>({ queryKey: ["purchase-requisitions"], queryFn: getPurchaseRequisitions });
  const detailQuery = useQuery({ queryKey: ["purchase-requisition", selectedRequisitionId], queryFn: () => getPurchaseRequisition(selectedRequisitionId!), enabled: selectedRequisitionId !== null });
  const traceabilityQuery = useQuery({ queryKey: ["purchase-requisition-traceability", selectedRequisitionId], queryFn: () => getPurchaseRequisitionTraceability(selectedRequisitionId!), enabled: selectedRequisitionId !== null });
  const approvalQuery = useQuery({ queryKey: ["approval-status", "PURCHASE_REQUISITION", selectedRequisitionId], queryFn: () => getApprovalStatus("PURCHASE_REQUISITION", selectedRequisitionId!), enabled: selectedRequisitionId !== null });

  const createMutation = useMutation({
    mutationFn: createPurchaseRequisition,
    onSuccess: () => {
      resetCreateForm();
      queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const submitMutation = useMutation({ mutationFn: submitPurchaseRequisition, onSuccess: invalidateWorkflow });
  const approveMutation = useMutation({ mutationFn: approvePurchaseRequisition, onSuccess: invalidateWorkflow });
  const rejectMutation = useMutation({ mutationFn: rejectPurchaseRequisition, onSuccess: invalidateWorkflow });

  const products = productsQuery.data ?? [];
  const requisitions = requisitionsQuery.data ?? [];
  const totalAmount = useMemo(() => lines.reduce((total, line) => total + line.quantity * line.estimated_price, 0), [lines]);
  const actionPending = submitMutation.isPending || approveMutation.isPending || rejectMutation.isPending;

  function invalidateWorkflow() {
    queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
    queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
  }

  function resetCreateForm() {
    setCreateOpen(false);
    setNotes("");
    setLines([]);
    setSelectedProductId("");
    setQuantity("");
    setEstimatedPrice("");
    createMutation.reset();
  }

  function addLine() {
    const productId = Number(selectedProductId);
    const lineQuantity = Number(quantity);
    const price = Number(estimatedPrice);
    if (!productId || lineQuantity <= 0 || price < 0) return;

    const existingLine = lines.find((line) => line.product_id === productId);
    if (existingLine) {
      setLines((current) => current.map((line) => line.product_id === productId ? { ...line, quantity: line.quantity + lineQuantity } : line));
    } else {
      setLines((current) => [...current, { product_id: productId, quantity: lineQuantity, estimated_price: price }]);
    }

    setSelectedProductId("");
    setQuantity("");
    setEstimatedPrice("");
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lines.length === 0) return;
    createMutation.mutate({ notes: notes || undefined, items: lines });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Purchase Requisitions"
        description="Request items for purchasing and follow the full document trail."
        actions={
          <>
            <Button type="button" variant="secondary" onClick={() => window.print()}><Printer size={16} className="mr-2" />Print</Button>
            <Button type="button" onClick={() => { createMutation.reset(); setCreateOpen(true); }}><Plus size={16} className="mr-2" />Create PR</Button>
          </>
        }
      />

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <h2 className="font-semibold text-slate-900">Purchase requisitions</h2>
            <p className="mt-1 text-sm text-slate-500">{requisitions.length} requests</p>
          </div>
        </div>

        {requisitionsQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading purchase requisitions...</div>}
        {requisitionsQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load purchase requisitions.</div>}

        {!requisitionsQuery.isLoading && !requisitionsQuery.isError && requisitions.length === 0 && <EmptyState title="No purchase requisitions yet" description="Create a PR to start the purchasing workflow." action={<Button type="button" onClick={() => setCreateOpen(true)}><Plus size={16} className="mr-2" />Create PR</Button>} />}

        {requisitions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px]">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">PR Number</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Date</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Total</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Action</th>
                </tr>
              </thead>
              <tbody>
                {requisitions.map((requisition) => (
                  <tr key={requisition.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-6 py-4 text-sm font-medium text-slate-900">{requisition.pr_number}</td>
                    <td className="px-6 py-4"><StatusBadge status={requisition.status} /></td>
                    <td className="px-6 py-4 text-sm text-slate-600">{requisition.request_date}</td>
                    <td className="px-6 py-4 text-right text-sm font-medium text-slate-900">{Number(requisition.total_amount).toFixed(2)}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <Button type="button" variant="secondary" onClick={() => setSelectedRequisitionId(requisition.id)}>View</Button>
                        {requisition.status === "DRAFT" && <Button type="button" onClick={() => submitMutation.mutate(requisition.id)} loading={submitMutation.isPending} disabled={actionPending}>Submit</Button>}
                        {requisition.status === "PENDING_APPROVAL" && <>
                          <Button type="button" onClick={() => approveMutation.mutate(requisition.id)} loading={approveMutation.isPending} disabled={actionPending}>Approve</Button>
                          <Button type="button" variant="danger" onClick={() => rejectMutation.mutate(requisition.id)} loading={rejectMutation.isPending} disabled={actionPending}>Reject</Button>
                        </>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={createOpen}
        onClose={resetCreateForm}
        title="Create purchase requisition"
        description="Add requested items and keep the PR estimate separate from the eventual PO price."
        size="lg"
        closeDisabled={createMutation.isPending}
        footer={<><Button type="button" variant="secondary" onClick={resetCreateForm} disabled={createMutation.isPending}>Cancel</Button><Button type="submit" form="create-pr-form" loading={createMutation.isPending} disabled={lines.length === 0}>Create PR</Button></>}
      >
        <form id="create-pr-form" onSubmit={handleSubmit} className="space-y-5">
          <section className="rounded-xl border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-900">Add products</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-[1fr_140px_160px_auto]">
              <Select value={selectedProductId} onChange={setSelectedProductId} placeholder="Select product" options={products.map((product) => ({ value: String(product.id), label: `${product.code} - ${product.name}` }))} />
              <input type="number" min="0.01" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="Quantity" className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
              <input type="number" min="0" step="0.01" value={estimatedPrice} onChange={(event) => setEstimatedPrice(event.target.value)} placeholder="Estimated price" className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
              <Button type="button" variant="secondary" onClick={addLine}>Add</Button>
            </div>
          </section>

          {lines.length > 0 && <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Requested items</h3>
            {lines.map((line) => {
              const product = products.find((item) => item.id === line.product_id);
              return <div key={line.product_id} className="flex items-center justify-between rounded-lg bg-slate-50 p-3">
                <div><p className="text-sm font-medium text-slate-900">{product?.name ?? "Product"}</p><p className="text-xs text-slate-500">{line.quantity} {product?.uom ?? ""} × {line.estimated_price}</p></div>
                <div className="flex items-center gap-3"><span className="text-sm font-medium text-slate-900">{(line.quantity * line.estimated_price).toFixed(2)}</span><button type="button" onClick={() => setLines((current) => current.filter((item) => item.product_id !== line.product_id))} className="text-xs font-medium text-red-600 hover:text-red-700">Remove</button></div>
              </div>;
            })}
            <div className="flex items-center justify-between border-t border-slate-200 pt-4"><span className="text-sm font-medium text-slate-600">Estimated total</span><span className="text-xl font-semibold text-slate-900">{totalAmount.toFixed(2)}</span></div>
          </section>}

          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} placeholder="Notes (optional)" className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" />
          {createMutation.isError && <p className="text-sm text-red-600">Failed to create purchase requisition.</p>}
        </form>
      </Modal>

      <Modal open={selectedRequisitionId !== null} onClose={() => setSelectedRequisitionId(null)} title="Purchase requisition details" description="Review stored items and the full document traceability chain." size="xl">
        {detailQuery.isLoading && <p className="text-sm text-slate-500">Loading requisition details...</p>}
        {detailQuery.isError && <p className="text-sm text-red-600">Failed to load requisition details.</p>}
        {detailQuery.data && <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3"><div><p className="text-xs uppercase tracking-wide text-slate-500">PR Number</p><p className="mt-1 text-sm font-medium text-slate-900">{detailQuery.data.pr_number}</p></div><div><p className="text-xs uppercase tracking-wide text-slate-500">Status</p><div className="mt-1"><StatusBadge status={detailQuery.data.status} /></div></div><div><p className="text-xs uppercase tracking-wide text-slate-500">Total</p><p className="mt-1 text-sm font-medium text-slate-900">{Number(detailQuery.data.total_amount).toFixed(2)}</p></div></div>

          <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[600px]"><thead><tr className="border-b border-slate-200 bg-slate-50 text-left"><th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Product</th><th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Qty</th><th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Est. Price</th><th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Total</th></tr></thead><tbody>{detailQuery.data.items.map((item) => <tr key={item.id} className="border-b border-slate-100 last:border-0"><td className="px-4 py-3"><p className="text-sm font-medium text-slate-900">{item.product_name}</p><p className="text-xs text-slate-500">{item.product_code}</p></td><td className="px-4 py-3 text-right text-sm text-slate-700">{item.quantity} {item.product_uom}</td><td className="px-4 py-3 text-right text-sm text-slate-700">{Number(item.estimated_price).toFixed(2)}</td><td className="px-4 py-3 text-right text-sm font-medium text-slate-900">{Number(item.total_price).toFixed(2)}</td></tr>)}</tbody></table></div>

          {approvalQuery.data && <div>
            <h3 className="text-sm font-semibold text-slate-900">Approval workflow</h3>
            <div className="mt-3 space-y-2">
              {approvalQuery.data.steps.map((step) => (
                <div key={step.step_order} className={`flex items-center justify-between rounded-lg border p-3 ${step.status === "PENDING" ? "border-slate-900 bg-slate-50" : "border-slate-200"}`}>
                  <div><p className="text-sm font-medium text-slate-900">{step.step_order}. {step.name}</p><p className="text-xs text-slate-500">{step.approver_role_name}{step.department_name ? ` · ${step.department_name}` : ""}{step.location_name ? ` · ${step.location_name}` : ""}</p></div>
                  <span className="text-xs font-semibold uppercase text-slate-500">{step.status}</span>
                </div>
              ))}
            </div>
            {approvalQuery.data.current_step_name && <p className="mt-2 text-xs text-slate-500">Current approval: {approvalQuery.data.current_step_name} ({approvalQuery.data.current_approver_role})</p>}
          </div>}

          <div><h3 className="text-sm font-semibold text-slate-900">Document traceability</h3><div className="mt-3 space-y-3">{traceabilityQuery.isLoading && <p className="text-sm text-slate-500">Loading traceability...</p>}{traceabilityQuery.data && <><div className="grid gap-3 sm:grid-cols-3"><div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">Purchase orders</p><p className="mt-1 text-lg font-semibold text-slate-900">{traceabilityQuery.data.purchase_orders.length}</p></div><div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">Goods receipts</p><p className="mt-1 text-lg font-semibold text-slate-900">{traceabilityQuery.data.goods_receipts.length}</p></div><div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">Stock movements</p><p className="mt-1 text-lg font-semibold text-slate-900">{traceabilityQuery.data.stock_movements.length}</p></div></div><div className="space-y-2">{traceabilityQuery.data.events.map((event) => <div key={event.id} className="flex items-start gap-3 rounded-lg border border-slate-200 p-3"><div className="mt-1 h-2 w-2 rounded-full bg-slate-900" /><div><p className="text-sm font-medium text-slate-900">{event.summary}</p><p className="mt-1 text-xs text-slate-500">{event.action} · {event.user_name ?? "System"} · {new Date(event.created_at).toLocaleString()}</p></div></div>)}</div></>}</div></div>
        </div>}
      </Modal>
    </div>
  );
}

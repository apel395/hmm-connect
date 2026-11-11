import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RotateCcw } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import CurrencyInput from "@/components/form/CurrencyInput";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Loading from "@/components/ui/Loading";
import useAuthorization from "@/hooks/useAuthorization";
import { prepareInvoiceFromReceipt } from "@/modules/finance/supplier-invoices/api";
import { destinationLabel } from "../destination";
import ReceivingDetailActions, { type ReceivingMenuAction, type ReceivingPrimaryAction } from "../components/ReceivingDetailActions";
import ReceivingDetailSections from "../components/ReceivingDetailSections";
import EditReceivingDialog from "../components/EditReceivingDialog";
import {
  useDepostGoodsReceipt,
  useApproveGoodsReceipt,
  useCorrectGoodsReceiptCosts,
  useCorrectHistoricalReceipt,
  useGoodsReceipt,
  usePostGoodsReceipt,
  useRejectGoodsReceipt,
  useReturnGoodsReceipt,
  useSubmitGoodsReceipt,
} from "../hooks/useGoodsReceipts";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

const receivingDate = (value?: string) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" :
    date.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Jakarta" });
};

export default function ReceivingDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const receiptId = Number(id);
  const { data, isLoading } = useGoodsReceipt(receiptId);
  const qc = useQueryClient();
  const { canPerform, isSuperuser, hasPermission } = useAuthorization();

  const prepareInvoice = useMutation({
    mutationFn: prepareInvoiceFromReceipt,
    onSuccess: invoice => {
      qc.invalidateQueries({ queryKey: ["goods-receipt", receiptId] });
      qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
      toast.success("Supplier invoice draft is ready for confirmation.");
      navigate("/supplier-invoices/" + invoice.id);
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Unable to prepare invoice draft"),
  });
  const depost = useDepostGoodsReceipt();
  const submitApproval = useSubmitGoodsReceipt();
  const approve = useApproveGoodsReceipt();
  const reject = useRejectGoodsReceipt();
  const post = usePostGoodsReceipt();
  const returned = useReturnGoodsReceipt();
  const correctCosts = useCorrectGoodsReceiptCosts();
  const correctHistorical = useCorrectHistoricalReceipt();

  const [depostOpen, setDepostOpen] = useState(false);
  const [depostReason, setDepostReason] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [costDialogOpen, setCostDialogOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [costs, setCosts] = useState<Record<number, number>>({});
  const [historicalOpen, setHistoricalOpen] = useState(false);
  const [historicalReason, setHistoricalReason] = useState("");
  const [historicalNumbers, setHistoricalNumbers] = useState<Record<number, { quantity: string; unit_cost: string }>>({});
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [returnOpen, setReturnOpen] = useState(false);

  useEffect(() => {
    if (data) setCosts(Object.fromEntries(data.items.map(item => [item.id, Number(item.unit_cost)])));
  }, [data]);

  if (isLoading) return <Loading />;
  if (!data) return null;

  const actions = data.allowed_actions;
  const historical = data.source_type === "HISTORICAL_ENTRY";
  const canSubmit = Boolean(actions?.can_submit) ||
    (isSuperuser() && !historical && data.status === "DRAFT" && !data.approval_status);
  const canApprove = data.approval_status === "PENDING" && Boolean(actions?.can_approve);
  const canReject = data.approval_status === "PENDING" && Boolean(actions?.can_reject);
  const canPost = canPerform("post", ["WAREHOUSE", "PURCHASING"], actions?.can_post ?? false, "receiving.post");
  const canReturn = canPerform("receive", ["WAREHOUSE", "PURCHASING"], actions?.can_return ?? false);

  const postReceipt = () => post.mutate(data.id, {
    onSuccess: () => toast.success("Receiving posted"),
    onError: error => {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Receiving could not be posted");
    },
  });
  const openCostCorrection = () => {
    setCosts(Object.fromEntries(data.items.map(item => [item.id, Number(item.unit_cost)])));
    setReason("");
    setCostDialogOpen(true);
  };
  const openHistoricalCorrection = () => {
    setHistoricalNumbers(Object.fromEntries(data.items.map(item => [item.id, {
      quantity: String(item.quantity), unit_cost: String(item.unit_cost),
    }])));
    setHistoricalReason("");
    setHistoricalOpen(true);
  };

  let primary: ReceivingPrimaryAction | undefined;
  if (canPost) {
    primary = { label: "Post Receiving", onClick: postReceipt, loading: post.isPending };
  } else if (canApprove) {
    primary = {
      label: "Approve Receiving",
      onClick: () => approve.mutate({ id: data.id }, { onSuccess: () => toast.success("Approval stage completed") }),
      loading: approve.isPending,
    };
  } else if (canSubmit) {
    primary = {
      label: "Submit for Approval",
      onClick: () => submitApproval.mutate(data.id, { onSuccess: () => toast.success("Receiving submitted for approval") }),
      loading: submitApproval.isPending,
    };
  } else if (data.status === "POSTED" && data.supplier_invoice_id && hasPermission("supplier_invoice.view")) {
    primary = {
      label: data.supplier_invoice_status === "DRAFT" ? "Review Supplier Invoice" : "View Supplier Invoice",
      icon: "invoice",
      onClick: () => navigate("/supplier-invoices/" + data.supplier_invoice_id),
    };
  } else if (data.status === "POSTED" && !data.supplier_invoice_id && hasPermission("supplier_invoice.create")) {
    primary = {
      label: "Prepare Supplier Invoice",
      icon: "prepare",
      loading: prepareInvoice.isPending,
      onClick: () => prepareInvoice.mutate(data.id),
    };
  }

  const menuActions: ReceivingMenuAction[] = [];
  if (actions?.can_edit) {
    menuActions.push({ label: "Edit Receiving", kind: "edit", onSelect: () => setEditOpen(true) });
  }
  if (actions?.can_depost && !historical) {
    menuActions.push({
      label: "Depost for Edit", kind: "depost",
      onSelect: () => { setDepostReason(""); setDepostOpen(true); },
    });
  }
  if (historical && data.status === "POSTED" && isSuperuser() && actions?.can_historical_correct) {
    menuActions.push({ label: "Correct Historical Numbers", kind: "historical", onSelect: openHistoricalCorrection });
  } else if (actions?.can_correct_cost) {
    menuActions.push({ label: "Correct Cost", kind: "cost", onSelect: openCostCorrection });
  }
  if (canReject) {
    menuActions.push({ label: "Reject Approval", kind: "reject", onSelect: () => setRejectOpen(true) });
  }
  if (canReturn) {
    menuActions.push({ label: "Return Goods", kind: "return", onSelect: () => setReturnOpen(true) });
  }

  const correctedTotal = data.items.reduce((sum, item) =>
    sum + Number(item.quantity) * Number(costs[item.id] ?? item.unit_cost), 0);
  const changedItems = data.items.filter(item =>
    Number(costs[item.id] ?? item.unit_cost) !== Number(item.unit_cost));
  const submitCostCorrection = async () => {
    if (!changedItems.length) return toast.error("Change at least one unit cost.");
    if (reason.trim().length < 3) return toast.error("Correction reason is required.");
    try {
      await correctCosts.mutateAsync({
        id: data.id,
        payload: {
          reason: reason.trim(),
          items: changedItems.map(item => ({ item_id: item.id, unit_cost: Number(costs[item.id]) })),
        },
      });
      toast.success("Receiving cost corrected.");
      setCostDialogOpen(false);
      setReason("");
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Cost correction failed");
    }
  };
  const historicalChanges = data.items.flatMap(item => {
    const inputs = historicalNumbers[item.id];
    if (!inputs) return [];
    const quantity = Number(inputs.quantity);
    const unit_cost = Number(inputs.unit_cost);
    if (!inputs.quantity.trim() || !inputs.unit_cost.trim() || !Number.isFinite(quantity) ||
        !Number.isFinite(unit_cost) || quantity <= 0 || unit_cost <= 0) return [];
    if (quantity === Number(item.quantity) && unit_cost === Number(item.unit_cost)) return [];
    return [{ item_id: item.id, quantity, unit_cost }];
  });
  const invalidHistoricalNumbers = data.items.some(item => {
    const inputs = historicalNumbers[item.id];
    return !inputs || !inputs.quantity.trim() || !inputs.unit_cost.trim() ||
      !Number.isFinite(Number(inputs.quantity)) || !Number.isFinite(Number(inputs.unit_cost)) ||
      Number(inputs.quantity) <= 0 || Number(inputs.unit_cost) <= 0;
  });
  const submitHistoricalCorrection = async () => {
    if (invalidHistoricalNumbers) return toast.error("Quantity and unit cost must be positive numbers.");
    if (!historicalChanges.length) return toast.error("Change at least one quantity or cost.");
    if (historicalReason.trim().length < 3) return toast.error("Correction reason is required.");
    try {
      await correctHistorical.mutateAsync({ id: data.id, payload: { reason: historicalReason.trim(), items: historicalChanges } });
      setHistoricalOpen(false);
      toast.success("Historical Receiving numbers corrected. No physical stock movement was created.");
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Historical correction could not be saved");
    }
  };

  return (
    <div className="space-y-5 pb-6">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-5 border-b border-slate-200 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">Receiving Report</p>
            <h1 className="break-words text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{data.receipt_number}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant={data.status === "POSTED" ? "success" : data.status === "RETURNED" ? "danger" : "warning"}>{data.status}</Badge>
              {data.approval_status && <Badge variant={data.approval_status === "APPROVED" ? "success" : data.approval_status === "REJECTED" ? "danger" : "warning"}>{data.approval_status}</Badge>}
              <Badge variant="secondary">{data.source_mode === "ML" ? "Market List" :
                data.source_mode === "DIRECT" ? "Direct Receiving" : "Purchase Order"}</Badge>
              {data.supplier_invoice_status && <Badge variant={data.supplier_invoice_status === "DRAFT" ? "warning" : "secondary"}>Invoice {data.supplier_invoice_status}</Badge>}
            </div>
          </div>
          <ReceivingDetailActions
            receiptId={data.id}
            receiptNumber={data.receipt_number}
            canPrint={actions?.can_print !== false}
            primary={primary}
            menuActions={menuActions}
          />
        </div>
        <dl className="grid grid-cols-2 gap-x-5 gap-y-5 px-4 py-5 sm:grid-cols-3 sm:px-6 lg:grid-cols-4 xl:grid-cols-6">
          <Info label="Supplier">{data.supplier_name ?? "—"}</Info>
          <Info label="Receiving Date">{receivingDate(data.received_at)}</Info>
          <Info label="Source Document">
            {data.purchase_order_id ? <Link className="font-medium text-emerald-700 hover:underline" to={"/purchase-orders/" + data.purchase_order_id}>{data.purchase_order_number}</Link> :
              data.market_list_id ? <Link className="font-medium text-emerald-700 hover:underline" to={"/market-lists/" + data.market_list_id}>{data.market_list_number ?? "Market List"}</Link> :
                "Direct Receiving"}
          </Info>
          <Info label="Business Unit">{data.business_unit_name ?? data.business_unit_id ?? "—"}</Info>
          <Info label="Location">{data.location_name ?? data.location_id ?? "—"}</Info>
          <Info label="Department">{data.department_name ?? data.department_id ?? "—"}</Info>
          {data.destination_type !== "DIRECT_USE" && <Info label="Warehouse">{data.warehouse_name ?? "—"}</Info>}
        </dl>
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 bg-slate-50/70 px-4 py-4 sm:px-6">
          <div className="text-sm text-slate-600">
            <span className="font-semibold text-slate-800">{data.items.length} received items</span>
            <span className="px-2 text-slate-300">•</span>
            {destinationLabel(data.destination_type)}
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Receiving Total</span>
            <strong className="text-lg tabular-nums text-emerald-800 sm:text-xl">Rp {money(data.total_amount)}</strong>
          </div>
        </div>
      </div>

      {!historical && data.status === "DRAFT" && data.approval_status !== "APPROVED" &&
        <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          Receiving is not posted yet. It must complete Store → Chef → PM/Camp Boss approval before posting.
        </div>}

      <ReceivingDetailSections receipt={data} />

      {actions?.can_edit && <EditReceivingDialog open={editOpen} receipt={data} onClose={() => setEditOpen(false)} />}

      <Dialog open={depostOpen} onOpenChange={value => !depost.isPending && setDepostOpen(value)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Depost Receiving for Edit</DialogTitle></DialogHeader>
          <DialogBody className="space-y-3">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              This returns Receiving to Draft, reverses stock movements, and resets its journal. The current automatic invoice draft will be withdrawn. Confirmed invoices and subsequent stock movements block Depost.
            </div>
            <label className="block text-sm font-medium">Correction reason *
              <textarea aria-label="Receiving depost reason" className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 p-3"
                maxLength={500} value={depostReason} disabled={depost.isPending}
                onChange={event => setDepostReason(event.target.value)} />
            </label>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" disabled={depost.isPending} onClick={() => setDepostOpen(false)}>Cancel</Button>
            <Button disabled={depostReason.trim().length < 3} loading={depost.isPending}
              onClick={() => depost.mutate({ id: data.id, reason: depostReason.trim() }, {
                onSuccess: () => {
                  setDepostOpen(false);
                  setEditOpen(true);
                  toast.success("Receiving deposted. Correct the draft, complete approval and post it again.");
                },
                onError: (error: any) => toast.error(error?.response?.data?.detail || "Receiving could not be deposted"),
              })}>Depost and Edit</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reject Receiving Approval</DialogTitle></DialogHeader>
          <DialogBody>
            <label className="block text-sm font-medium">Reason *
              <textarea className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 p-3"
                value={rejectComment} onChange={event => setRejectComment(event.target.value)} />
            </label>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>Cancel</Button>
            <Button variant="danger" disabled={!rejectComment.trim()} loading={reject.isPending}
              onClick={() => reject.mutate({ id: data.id, comment: rejectComment.trim() }, {
                onSuccess: () => { toast.success("Receiving rejected"); setRejectOpen(false); setRejectComment(""); },
              })}>Reject</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={returnOpen} onOpenChange={value => !returned.isPending && setReturnOpen(value)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Return Received Goods?</DialogTitle></DialogHeader>
          <DialogBody>
            <div className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <AlertTriangle className="mt-0.5 shrink-0" size={18} />
              <p>This returns all quantities from {data.receipt_number}. Stock and linked accounting will be affected. Review the document before continuing.</p>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" disabled={returned.isPending} onClick={() => setReturnOpen(false)}>Cancel</Button>
            <Button variant="danger" loading={returned.isPending}
              onClick={() => returned.mutate(data.id, {
                onSuccess: () => { setReturnOpen(false); toast.success("Receiving returned"); },
                onError: (error: any) => toast.error(error?.response?.data?.detail || "Unable to return Receiving"),
              })}><RotateCcw size={16} /> Return Goods</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={costDialogOpen} onOpenChange={setCostDialogOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader><DialogTitle>Correct Receiving Cost</DialogTitle></DialogHeader>
          <DialogBody className="space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Cost corrections are audited. The backend blocks unsafe historical revaluation when downstream documents depend on this receipt.
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="bg-slate-50">
                  <tr><th className="p-3 text-left">Item</th><th className="p-3 text-right">Qty</th>
                    <th className="p-3 text-right">Current Cost</th><th className="p-3">Corrected Cost</th>
                    <th className="p-3 text-right">Amount</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map(item => <tr key={item.id}>
                    <td className="p-3">{item.product_name}</td>
                    <td className="p-3 text-right">{item.quantity}</td>
                    <td className="p-3 text-right">{money(item.unit_cost)}</td>
                    <td className="p-3"><CurrencyInput value={Number(costs[item.id] ?? item.unit_cost)}
                      onValueChange={value => setCosts(current => ({ ...current, [item.id]: value }))} /></td>
                    <td className="p-3 text-right">{money(Number(item.quantity) * Number(costs[item.id] ?? item.unit_cost))}</td>
                  </tr>)}
                </tbody>
                <tfoot className="bg-slate-50">
                  <tr><td colSpan={4} className="p-3 text-right font-semibold">Corrected Total</td>
                    <td className="p-3 text-right font-bold">{money(correctedTotal)}</td></tr>
                </tfoot>
              </table>
            </div>
            <label className="block text-sm font-medium">Correction Reason *
              <textarea className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 p-3"
                value={reason} onChange={event => setReason(event.target.value)} />
            </label>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCostDialogOpen(false)}>Cancel</Button>
            <Button loading={correctCosts.isPending} onClick={submitCostCorrection}>Save Correction</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={historicalOpen} onOpenChange={value => !correctHistorical.isPending && setHistoricalOpen(value)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader><DialogTitle>Correct Historical Receiving Numbers</DialogTitle></DialogHeader>
          <DialogBody className="space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Administrator correction for historical entry only. This updates recorded quantities, inventory values,
              the open journal, and the untouched invoice draft. It does not create physical stock IN/OUT movements.
              Posted financial dependencies or actual stock usage will block the correction.
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="bg-slate-50">
                  <tr><th className="p-3 text-left">Item</th><th className="p-3 text-right">Previous Qty</th>
                    <th className="p-3">Correct Qty</th><th className="p-3 text-right">Previous Cost</th>
                    <th className="p-3">Correct Cost</th><th className="p-3 text-right">New Subtotal</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map(item => <tr key={item.id}>
                    <td className="p-3">{item.product_name}</td>
                    <td className="p-3 text-right">{item.quantity}</td>
                    <td className="p-3"><input type="number" min="0.0001" step="any"
                      aria-label={`Correct quantity for ${item.product_name}`}
                      className="w-28 rounded-lg border border-slate-300 px-2 py-2 text-right"
                      value={historicalNumbers[item.id]?.quantity ?? ""} disabled={correctHistorical.isPending}
                      onChange={event => setHistoricalNumbers(current => ({ ...current, [item.id]: {
                        quantity: event.target.value, unit_cost: current[item.id]?.unit_cost ?? String(item.unit_cost),
                      } }))} /></td>
                    <td className="p-3 text-right">{money(item.unit_cost)}</td>
                    <td className="p-3"><input type="number" min="0.0001" step="any"
                      aria-label={`Correct unit cost for ${item.product_name}`}
                      className="w-36 rounded-lg border border-slate-300 px-2 py-2 text-right"
                      value={historicalNumbers[item.id]?.unit_cost ?? ""} disabled={correctHistorical.isPending}
                      onChange={event => setHistoricalNumbers(current => ({ ...current, [item.id]: {
                        quantity: current[item.id]?.quantity ?? String(item.quantity), unit_cost: event.target.value,
                      } }))} /></td>
                    <td className="p-3 text-right">{money(Number(historicalNumbers[item.id]?.quantity ?? item.quantity) * Number(historicalNumbers[item.id]?.unit_cost ?? item.unit_cost))}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
            <label className="block text-sm font-medium">Correction Reason *
              <textarea className="mt-1 min-h-20 w-full rounded-lg border border-slate-300 p-3"
                maxLength={500} value={historicalReason} disabled={correctHistorical.isPending}
                onChange={event => setHistoricalReason(event.target.value)} />
            </label>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" disabled={correctHistorical.isPending} onClick={() => setHistoricalOpen(false)}>Cancel</Button>
            <Button loading={correctHistorical.isPending}
              disabled={invalidHistoricalNumbers || !historicalChanges.length || historicalReason.trim().length < 3}
              onClick={submitHistoricalCorrection}>Save Historical Correction</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="min-w-0"><dt className="mb-1 text-xs text-slate-500">{label}</dt>
    <dd className="break-words text-sm font-medium text-slate-800">{children}</dd></div>;
}

import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import ModuleSummary from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Button from "@/components/ui/Button";
import Card, { CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import APWorkspaceHeader from "@/modules/finance/accounts-payable/APWorkspaceHeader";
import RejectDialog from "@/modules/purchasing/components/RejectDialog";
import { approveVoucher, getVoucher, rejectVoucher, submitVoucher, voidVoucher } from "../api";

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function PaymentVoucherDetailPage() {
  const { id } = useParams();
  const voucherId = Number(id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [rejectOpen, setRejectOpen] = useState(false);

  const query = useQuery({
    queryKey: ["payment-voucher", voucherId],
    queryFn: async () => (await getVoucher(voucherId)).data,
  });

  const invalidator = () => {
    qc.invalidateQueries({ queryKey: ["payment-voucher", voucherId] });
    qc.invalidateQueries({ queryKey: ["payment-vouchers"] });
    qc.invalidateQueries({ queryKey: ["payments"] });
  };
  const submit = useMutation({
    mutationFn: () => submitVoucher(voucherId),
    onSuccess: () => { toast.success("Voucher submitted for approval"); invalidator(); },
    onError: (error: any) => toast.error(error.response?.data?.detail || String(error)),
  });
  const approve = useMutation({
    mutationFn: () => approveVoucher(voucherId),
    onSuccess: () => { toast.success("Voucher approved — create the payment separately"); invalidator(); },
    onError: (error: any) => toast.error(error.response?.data?.detail || String(error)),
  });
  const reject = useMutation({
    mutationFn: (reason: string) => rejectVoucher(voucherId, reason),
    onSuccess: () => { setRejectOpen(false); toast.success("Voucher rejected"); invalidator(); },
    onError: (error: any) => toast.error(error.response?.data?.detail || String(error)),
  });
  const voidIt = useMutation({
    mutationFn: () => voidVoucher(voucherId),
    onSuccess: () => { toast.success("Voucher voided"); invalidator(); navigate("/finance/payment-vouchers"); },
    onError: (error: any) => toast.error(error.response?.data?.detail || String(error)),
  });

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        {query.isPending ? (
          <Card className="p-0"><Loading message="Loading payment voucher..." /></Card>
        ) : query.isError || !query.data ? (
          <Card className="p-0">
            <div role="alert" className="m-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div className="font-semibold">Payment voucher could not be loaded.</div>
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => query.refetch()}>Try again</Button>
                <Button size="sm" variant="outline" onClick={() => navigate("/finance/payment-vouchers")}>Back to Vouchers</Button>
              </div>
            </div>
          </Card>
        ) : (
          <VoucherDetail
            voucher={query.data as any}
            actions={
              <>
                <WorkspaceBackButton />
                {(query.data as any).allowed_actions?.can_print !== false && (
                  <PrintPreviewButton
                    src={`/finance/payment-vouchers/${voucherId}/print`}
                    title={`Payment Voucher ${(query.data as any).voucher_number}`}
                    ariaLabel="Preview payment voucher"
                  />
                )}
                {(query.data as any).allowed_actions?.can_submit && (
                  <Button loading={submit.isPending} onClick={() => submit.mutate()}>Submit for Approval</Button>
                )}
                {(query.data as any).allowed_actions?.can_approve && (
                  <Button loading={approve.isPending} onClick={() => approve.mutate()}>Approve Voucher</Button>
                )}
                {(query.data as any).allowed_actions?.can_reject && (
                  <Button variant="danger" onClick={() => setRejectOpen(true)}>Reject</Button>
                )}
                {(query.data as any).allowed_actions?.can_void && (
                  <Button variant="outline" loading={voidIt.isPending} onClick={() => voidIt.mutate()}>Void</Button>
                )}
              </>
            }
            onCreatePayment={() => {
              const groups = (query.data as any).groups ?? [];
              navigate("/payments", {
                state: {
                  editPayment: null,
                  voucherId,
                  voucherSupplierId: groups[0]?.supplier_id,
                },
              });
            }}
          />
        )}
      </div>

      <RejectDialog
        open={rejectOpen}
        onClose={() => setRejectOpen(false)}
        pending={reject.isPending}
        onReject={async (reason) => { await reject.mutateAsync(reason); }}
        title="Reject Payment Voucher"
        label="Reason for rejecting this voucher"
      />
    </DataWorkspace>
  );
}

function VoucherDetail({
  voucher,
  actions,
  onCreatePayment,
}: {
  voucher: any;
  actions: ReactNode;
  onCreatePayment: () => void;
}) {
  const allowed = voucher.allowed_actions ?? {};

  return (
    <>
      <PageHeader
        title={voucher.voucher_number}
        description={`${voucher.location_name ?? "Location pending"} • ${voucher.voucher_date} • ${voucher.status?.replaceAll("_", " ")}`}
        actions={actions}
      >
        <div className="mt-0.5 text-[11px] text-slate-500">Approval document only · no GL posting from vouchers</div>
      </PageHeader>
      <APWorkspaceHeader />

      {!allowed.can_submit && !allowed.can_approve && !allowed.can_reject && !allowed.can_void && (
        <div role="status" className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          This voucher has no actions available in its current state.
        </div>
      )}

      <ModuleSummary
        metrics={[
          { label: "Voucher total", value: money(voucher.total_amount) },
          { label: "Status", value: voucher.status?.replaceAll("_", " ") ?? "—" },
          { label: "Period", value: `${voucher.period_from || "—"} → ${voucher.period_to || "—"}` },
          { label: "Supplier groups", value: voucher.groups?.length ?? 0 },
          { label: "Allocated invoices", value: voucher.allocations?.length ?? 0 },
        ]}
      />

      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-sm">Payment Follow-up</CardTitle>
            <CardDescription>Approving a voucher reserves nothing and posts nothing. Create the payment separately to allocate cash.</CardDescription>
          </div>
        </CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm">
          <div>
            <div className="text-xs uppercase text-slate-500">Linked payment</div>
            <div className="mt-1">
              {voucher.payment_id ? (
                <Link className="font-medium text-emerald-700 hover:underline" to={`/payments/${voucher.payment_id}`}>
                  Open Payment #{voucher.payment_id}
                </Link>
              ) : voucher.status === "APPROVED" ? (
                "Approved — no payment created yet"
              ) : (
                "Available after approval"
              )}
            </div>
          </div>
          {voucher.status === "APPROVED" && !voucher.payment_id && (
            <Button size="sm" onClick={onCreatePayment}>Create Payment</Button>
          )}
        </div>
      </Card>

      {(voucher.groups?.length ?? 0) === 0 ? (
        <Card className="p-10 text-center text-sm text-slate-500">This voucher has no supplier groups.</Card>
      ) : (
        voucher.groups.map((group: any) => (
          <Card key={group.supplier_id} className="overflow-hidden p-0">
            <CardHeader>
              <div>
                <CardTitle className="text-sm">
                  {group.supplier_name} <span className="font-mono text-xs font-normal text-slate-500">{group.supplier_code}</span>
                </CardTitle>
                <CardDescription>
                  {group.bank
                    ? `${group.bank.bank_name} — ${group.bank.account_number} (${group.bank.account_name})`
                    : "Bank not set on supplier"}
                </CardDescription>
              </div>
              <div className="text-right">
                <div className="text-[11px] uppercase text-slate-500">Supplier total</div>
                <div className="font-semibold tabular-nums">{money(group.total)}</div>
              </div>
            </CardHeader>
            <Table className="min-w-[900px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
              <THead>
                <TR><TH>Invoice</TH><TH>Date</TH><TH>Due</TH><TH numeric>Total</TH><TH numeric>Allocated</TH></TR>
              </THead>
              <TBody>
                {(group.invoices ?? []).map((invoice: any) => (
                  <TR key={invoice.id}>
                    <TD>
                      <TableCellStack
                        primary={<Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${invoice.id}`}>{invoice.invoice_number}</Link>}
                        secondary={invoice.supplier_invoice_number}
                      />
                    </TD>
                    <TD className="whitespace-nowrap">{invoice.invoice_date}</TD>
                    <TD className="whitespace-nowrap">{invoice.due_date || "—"}</TD>
                    <TD numeric>{money(invoice.total_amount)}</TD>
                    <TD numeric className="font-semibold tabular-nums">{money(invoice.allocated_amount)}</TD>
                  </TR>
                ))}
                {!group.invoices?.length && (
                  <TR><TD colSpan={5} className="p-8 text-center text-slate-500">No invoices in this supplier group.</TD></TR>
                )}
              </TBody>
            </Table>
          </Card>
        ))
      )}
    </>
  );
}

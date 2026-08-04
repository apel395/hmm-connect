import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { createPayment, eligibleInvoices, listPayments } from "./api";
const methods = [
  "BANK_TRANSFER",
  "CASH",
  "CHEQUE",
  "CREDIT_CARD",
  "PETTY_CASH",
  "OTHER",
];
export default function PaymentListPage() {
  const nav = useNavigate(),
    qc = useQueryClient(),
    [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [method, setMethod] = useState(""),
    [supplierFilter, setSupplierFilter] = useState(""),
    [dateFrom, setDateFrom] = useState(""),
    [dateTo, setDateTo] = useState(""),
    [open, setOpen] = useState(false),
    [form, setForm] = useState<any>({
      supplier_id: 0,
      payment_date: new Date().toISOString().slice(0, 10),
      payment_method: "BANK_TRANSFER",
      payment_account_id: 0,
      currency: "IDR",
      total_amount: 0,
      reference_number: "",
      cheque_number: "",
      notes: "",
      source_type: "LIVE",
      allocations: [],
    });
  const q = useQuery({
      queryKey: ["payments", page, search, status, method, supplierFilter, dateFrom, dateTo],
      queryFn: () =>
        listPayments({
          page,
          page_size: 20,
          search: search || undefined,
          status: status || undefined,
          payment_method: method || undefined,
          supplier_id: supplierFilter || undefined,
          payment_date_from: dateFrom || undefined,
          payment_date_to: dateTo || undefined,
        }),
    }),
    { data: suppliers = [] } = useSuppliers(),
    accounts = useQuery({
      queryKey: ["payment-accounts"],
      queryFn: () =>
        getAccountLookup({
          account_type: "ASSET",
          is_posting: true,
          is_active: true,
        }),
    }),
    eligible = useQuery({
      queryKey: ["eligible-payment-invoices", form.supplier_id, form.currency],
      queryFn: () => eligibleInvoices(form.supplier_id, form.currency),
      enabled: !!form.supplier_id,
    });
  useEffect(
    () => setForm((f: any) => ({ ...f, allocations: [] })),
    [form.supplier_id],
  );
  const allocated = form.allocations.reduce(
    (s: number, a: any) => s + Number(a.allocated_amount),
    0,
  );
  const setAllocation = (id: number, amount: number) =>
    setForm({
      ...form,
      allocations:
        amount > 0
          ? [
              ...form.allocations.filter(
                (a: any) => a.supplier_invoice_id !== id,
              ),
              { supplier_invoice_id: id, allocated_amount: amount },
            ]
          : form.allocations.filter((a: any) => a.supplier_invoice_id !== id),
    });
  const save = useMutation({
    mutationFn: () => createPayment(form),
    onSuccess: (x) => {
      toast.success("Payment saved as draft");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["payments"] });
      nav(`/payments/${x.id}`);
    },
    onError: (e: any) =>
      toast.error(e.response?.data?.detail || "Payment could not be saved"),
  });
  const input = "h-10 w-full rounded border px-3";
  return (
    <>
      <PageHeader
        title="Payments"
        description="Allocate supplier payments and prepare cash-out journals."
        actions={<Button onClick={() => setOpen(true)}>Create Payment</Button>}
      />
      <Card>
        <div className="mb-4 grid gap-2 md:grid-cols-3 lg:grid-cols-6">
          <input
            className={input}
            placeholder="Search payments"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select className={input} value={supplierFilter} onChange={(e) => setSupplierFilter(e.target.value)}>
            <option value="">All suppliers</option>
            {suppliers.map((supplier: any) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
          </select>
          <select
            className={input}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {["DRAFT", "APPROVED", "POSTED", "VOID"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <select
            className={input}
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            <option value="">All methods</option>
            {methods.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <input aria-label="Payment date from" type="date" className={input} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input aria-label="Payment date to" type="date" className={input} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-[1200px] w-full text-sm">
            <thead>
              <tr>
                <th>Payment Number</th>
                <th>Payment Date</th>
                <th>Supplier</th>
                <th>Payment Method</th>
                <th>Payment Account</th>
                <th>Reference Number</th>
                <th>Amount</th>
                <th>Allocated Amount</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.items.map((x: any) => (
                <tr key={x.id} className="border-t">
                  <td>{x.payment_number}</td>
                  <td>{x.payment_date}</td>
                  <td>{x.supplier_name || "Legacy"}</td>
                  <td>{x.payment_method}</td>
                  <td>{x.payment_account_name || "—"}</td>
                  <td>{x.reference_number || "—"}</td>
                  <td>{Number(x.total_amount).toLocaleString()}</td>
                  <td>{Number(x.allocated_amount).toLocaleString()}</td>
                  <td>{x.status}</td>
                  <td>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => nav(`/payments/${x.id}`)}
                    >
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="outline"
            disabled={!q.data?.has_previous}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={!q.data?.has_next}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      </Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Create Payment</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (allocated !== Number(form.total_amount))
                return toast.error("Total allocated must equal payment total");
              save.mutate();
            }}
          >
            <DialogBody className="space-y-5">
              <div className="grid gap-3 md:grid-cols-3">
                <label>
                  Supplier
                  <select
                    required
                    className={input}
                    value={form.supplier_id}
                    onChange={(e) =>
                      setForm({ ...form, supplier_id: Number(e.target.value) })
                    }
                  >
                    <option value={0}>Select supplier</option>
                    {suppliers.map((s: any) => (
                      <option key={s.id} value={s.id}>
                        {s.code} — {s.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Payment Date
                  <input
                    type="date"
                    className={input}
                    value={form.payment_date}
                    onChange={(e) =>
                      setForm({ ...form, payment_date: e.target.value })
                    }
                  />
                </label>
                <label>
                  Payment Method
                  <select
                    className={input}
                    value={form.payment_method}
                    onChange={(e) =>
                      setForm({ ...form, payment_method: e.target.value })
                    }
                  >
                    {methods.map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Payment Account
                  <select
                    required
                    className={input}
                    value={form.payment_account_id}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        payment_account_id: Number(e.target.value),
                      })
                    }
                  >
                    <option value={0}>Select bank/cash account</option>
                    {accounts.data?.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.account_code} — {a.account_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Currency
                  <input
                    className={input}
                    value={form.currency}
                    onChange={(e) =>
                      setForm({ ...form, currency: e.target.value })
                    }
                  />
                </label>
                <label>
                  Payment Total
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    className={input}
                    value={form.total_amount}
                    onChange={(e) =>
                      setForm({ ...form, total_amount: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  Reference Number
                  <input
                    className={input}
                    value={form.reference_number}
                    onChange={(e) =>
                      setForm({ ...form, reference_number: e.target.value })
                    }
                  />
                </label>
                {form.payment_method === "CHEQUE" && (
                  <label>
                    Cheque Number
                    <input
                      className={input}
                      value={form.cheque_number}
                      onChange={(e) =>
                        setForm({ ...form, cheque_number: e.target.value })
                      }
                    />
                  </label>
                )}
              </div>
              <table className="table-grid w-full text-sm">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Date</th>
                    <th>Due</th>
                    <th>Total</th>
                    <th>Paid</th>
                    <th>Outstanding</th>
                    <th>Allocation</th>
                  </tr>
                </thead>
                <tbody>
                  {eligible.data?.map((x: any) => (
                    <tr key={x.id} className="border-t">
                      <td>{x.invoice_number}</td>
                      <td>{x.invoice_date}</td>
                      <td>{x.due_date || "—"}</td>
                      <td>{Number(x.total_amount).toLocaleString()}</td>
                      <td>{Number(x.paid_amount).toLocaleString()}</td>
                      <td>{Number(x.outstanding_balance).toLocaleString()}</td>
                      <td>
                        <input
                          aria-label={`Allocation for ${x.invoice_number}`}
                          className={input}
                          type="number"
                          min="0"
                          max={x.outstanding_balance}
                          onChange={(e) =>
                            setAllocation(x.id, Number(e.target.value))
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="grid grid-cols-3 text-right">
                <div>
                  Payment Total: {Number(form.total_amount).toLocaleString()}
                </div>
                <div>Total Allocated: {allocated.toLocaleString()}</div>
                <div>
                  Remaining:{" "}
                  {(Number(form.total_amount) - allocated).toLocaleString()}
                </div>
              </div>
              <textarea
                className="w-full rounded border p-2"
                placeholder="Notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </DialogBody>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" loading={save.isPending}>
                Save Draft
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

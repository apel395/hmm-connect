import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import { todayLocal } from "@/utils/dateConstraints";

export type ReturnEvent = {
  id: number;
  kind: string;
  date: string;
  amount: number;
  reference: string;
  reason: string;
  journal_entry_id: number;
  reversed: boolean;
};
type Props = {
  id: number;
  status: string;
  balance: number;
  history: ReturnEvent[];
  canManage: boolean;
  pending: boolean;
  accounts: Array<{
    id: number;
    account_code: string;
    account_name: string;
    account_type?: string;
    account_subtype?: string | null;
  }>;
  submit: (value: { path: string; data: unknown }) => void;
};
const input =
  "h-9 w-full min-w-0 rounded-md border border-slate-300 bg-white px-2 text-sm";
const label = "flex min-w-0 flex-col gap-1 text-xs text-slate-600";
const money = (v: number) =>
  Number(v).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function ReturnCompletion({
  id,
  status,
  balance,
  history,
  canManage,
  pending,
  accounts,
  submit,
}: Props) {
  const [kind, setKind] = useState("APPLY");
  const [date, setDate] = useState(todayLocal);
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState("");
  const [invoice, setInvoice] = useState("");
  const [bank, setBank] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [requestKey] = useState(() => crypto.randomUUID());
  const [correction, setCorrection] = useState("");
  const [correctionDate, setCorrectionDate] = useState(todayLocal);
  const [correctionRef, setCorrectionRef] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionKey] = useState(() => crypto.randomUUID());
  const invoices = useQuery({
    queryKey: ["inventory-credit-invoices", id, search, page],
    queryFn: async () =>
      (
        await api.get<{
          items: Array<{ id: number; number: string; balance: number }>;
          total_pages: number;
        }>(`/inventory/returns/${id}/credit-invoices`, {
          params: { search, page },
        })
      ).data,
    enabled:
      canManage && status === "POSTED" && balance > 0 && kind === "APPLY",
  });
  const hasActiveUse = history.some(
    (e) => (e.kind === "APPLY" || e.kind === "REFUND") && !e.reversed,
  );
  const canSubmit =
    !pending &&
    !!date &&
    !!reference.trim() &&
    !!reason.trim() &&
    Number(amount) > 0 &&
    Number(amount) <= balance &&
    (kind === "APPLY" ? !!invoice : !!bank);
  const correctionPayload = {
    request_key: correctionKey,
    event_date: correctionDate,
    reference: correctionRef,
    reason: correctionReason,
  };
  return (
    <div className="space-y-3 border-t pt-3">
      {status === "POSTED" && balance > 0 && (
        <div className="flex justify-between text-sm">
          <span>Available supplier credit</span>
          <strong>{money(balance)}</strong>
        </div>
      )}
      {canManage && status === "POSTED" && balance > 0 && (
        <details className="rounded-md border p-3">
          <summary className="cursor-pointer text-sm font-medium text-emerald-800">
            Use / refund supplier credit
          </summary>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <label className={label}>
              Action
              <select
                className={input}
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="APPLY">Apply to invoice</option>
                <option value="REFUND">Supplier refund</option>
              </select>
            </label>
            <label className={label}>
              Transaction date
              <input
                className={input}
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <label className={label}>
              Amount
              <input
                className={input}
                type="number"
                min="0.01"
                step="0.01"
                max={balance}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            {kind === "APPLY" ? (
              <div className="space-y-2 md:col-span-3">
                <label className={label}>
                  Search supplier invoices
                  <input
                    className={input}
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPage(1);
                    }}
                  />
                </label>
                <label className={label}>
                  Target invoice
                  <select
                    className={input}
                    value={invoice}
                    onChange={(e) => setInvoice(e.target.value)}
                  >
                    <option value="">Select invoice</option>
                    {invoices.data?.items.map((i) => (
                      <option value={i.id} key={i.id}>
                        {i.number} · due {money(i.balance)}
                      </option>
                    ))}
                  </select>
                </label>
                {invoices.isError && (
                  <p role="alert" className="text-xs text-red-700">
                    Unable to load eligible invoices. Retry using Refresh.
                  </p>
                )}
                {invoices.data && invoices.data.items.length === 0 && (
                  <p className="text-xs text-slate-500">
                    No eligible outstanding invoices for this supplier and
                    location.
                  </p>
                )}
                {(invoices.data?.total_pages ?? 0) > 1 && (
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      disabled={page >= (invoices.data?.total_pages ?? 1)}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <label className={`${label} md:col-span-3`}>
                Refund cash / bank account
                <select
                  className={input}
                  value={bank}
                  onChange={(e) => setBank(e.target.value)}
                >
                  <option value="">Select cash / bank</option>
                  {accounts
                    .filter(
                      (a) =>
                        a.account_type === "ASSET" &&
                        [
                          "BANK",
                          "CASH",
                          "PETTY_CASH",
                          "CASH_AND_BANK",
                        ].includes(a.account_subtype ?? ""),
                    )
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.account_code} — {a.account_name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            <label className={label}>
              Reference
              <input
                className={input}
                value={reference}
                onChange={(e) => setReference(e.target.value)}
              />
            </label>
            <label className={`${label} md:col-span-2`}>
              Reason
              <input
                className={input}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
          </div>
          <Button
            className="mt-3"
            disabled={!canSubmit}
            onClick={() =>
              submit({
                path: `/inventory/returns/${id}/credit-use`,
                data: {
                  request_key: requestKey,
                  kind,
                  event_date: date,
                  reference,
                  reason,
                  amount: Number(amount),
                  supplier_invoice_id:
                    kind === "APPLY" ? Number(invoice) : null,
                  cash_account_id: kind === "REFUND" ? Number(bank) : null,
                },
              })
            }
          >
            Post {kind === "APPLY" ? "Credit Application" : "Supplier Refund"}
          </Button>
        </details>
      )}
      {history.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left">
                <th className="py-2">Date</th>
                <th>Action</th>
                <th>Reference / reason</th>
                <th className="text-right">Amount</th>
                <th>Journal</th>
              </tr>
            </thead>
            <tbody>
              {history.map((e) => (
                <tr className="border-b" key={e.id}>
                  <td className="py-2">{e.date}</td>
                  <td>
                    {e.kind.replaceAll("_", " ")}
                    {e.reversed ? " · reversed" : ""}
                  </td>
                  <td>
                    {e.reference}
                    <div className="text-slate-500">{e.reason}</div>
                  </td>
                  <td className="text-right">{money(e.amount)}</td>
                  <td>
                    <Link
                      className="text-emerald-700 underline"
                      to={`/journal-entries/${e.journal_entry_id}`}
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canManage && status === "POSTED" && (
        <details className="rounded-md border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            Correct posted return
          </summary>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <label className={label}>
              Reverse
              <select
                className={input}
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
              >
                <option value="">Select transaction</option>
                {history
                  .filter(
                    (e) =>
                      (e.kind === "APPLY" || e.kind === "REFUND") &&
                      !e.reversed,
                  )
                  .map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.kind} · {e.reference} · {money(e.amount)}
                    </option>
                  ))}
                <option value="RETURN" disabled={hasActiveUse}>
                  Entire return and its replacement / credit entries
                </option>
              </select>
            </label>
            <label className={label}>
              Reversal date
              <input
                type="date"
                className={input}
                value={correctionDate}
                onChange={(e) => setCorrectionDate(e.target.value)}
              />
            </label>
            <label className={label}>
              Correction reference
              <input
                className={input}
                value={correctionRef}
                onChange={(e) => setCorrectionRef(e.target.value)}
              />
            </label>
            <label className={label}>
              Correction reason
              <input
                className={input}
                value={correctionReason}
                onChange={(e) => setCorrectionReason(e.target.value)}
              />
            </label>
          </div>
          {hasActiveUse && (
            <p className="mt-2 text-xs text-slate-500">
              Reverse active credit applications/refunds first.
            </p>
          )}
          <Button
            variant="outline"
            className="mt-3"
            disabled={
              pending ||
              !correction ||
              !correctionDate ||
              !correctionRef.trim() ||
              !correctionReason.trim()
            }
            onClick={() =>
              submit({
                path:
                  correction === "RETURN"
                    ? `/inventory/returns/${id}/reverse`
                    : `/inventory/returns/${id}/events/${correction}/reverse`,
                data: correctionPayload,
              })
            }
          >
            Post Reversal
          </Button>
        </details>
      )}
    </div>
  );
}

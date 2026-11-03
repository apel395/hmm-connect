import ReturnCompletion, { type ReturnEvent } from "./ReturnCompletion";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import useAuthorization from "@/hooks/useAuthorization";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { todayLocal } from "@/utils/dateConstraints";

const input =
  "h-9 w-full min-w-0 rounded-md border border-slate-300 bg-white px-2 text-sm";
const label = "flex min-w-0 flex-col gap-1 text-xs text-slate-600";
const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
const quantity = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });
type SourceLine = {
  id: number;
  code: string;
  name: string;
  uom: string;
  received: number;
  returned: number;
  remaining: number;
  available: number;
};
type ReturnLine = {
  id: number;
  product_id: number;
  code: string;
  name: string;
  uom: string;
  quantity: number;
  replaced_quantity: number;
  line_cost: number;
};
type ReturnDocument = {
  id: number;
  number: string;
  goods_receipt_id: number;
  warehouse_id: number;
  receipt_number: string;
  supplier_name: string;
  purpose: string;
  status: string;
  reason: string;
  return_date: string;
  total_cost: number;
  clearing_balance: number;
  journal_entry_id: number | null;
  credit_journal_id: number | null;
  credit_reference: string | null;
  credit_applied: number | null;
  supplier_credit: number | null;
  items: ReturnLine[];
  remaining_supplier_credit: number;
  events: ReturnEvent[];
  replacement_receipts: Array<{ id: number; number: string }>;
};
type Source = {
  id: number;
  warehouse_id: number;
  number: string;
  supplier: string;
  items: SourceLine[];
  invoices: Array<{
    id: number;
    number: string;
    status: string;
    balance: number;
    total: number;
  }>;
};

export default function InventoryReturnsPage() {
  const auth = useAuthorization();
  const can = (permission: string) =>
    auth.isSuperuser() || auth.hasPermission(permission);
  const [params, setParams] = useSearchParams();
  const id = Number(params.get("id")) || undefined;
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [creating, setCreating] = useState(false);
  const [sourceSearch, setSourceSearch] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [receiptId, setReceiptId] = useState("");
  const [purpose, setPurpose] = useState("REPLACEMENT");
  const [date, setDate] = useState(todayLocal);
  const [reason, setReason] = useState("");
  const [clearing, setClearing] = useState("");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [replacementQty, setReplacementQty] = useState<Record<number, string>>(
    {},
  );
  const [replacementDate, setReplacementDate] = useState(todayLocal);
  const [deliveryNote, setDeliveryNote] = useState("");
  const [invoiceId, setInvoiceId] = useState("");
  const [creditDate, setCreditDate] = useState(todayLocal);
  const [creditRef, setCreditRef] = useState("");
  const [net, setNet] = useState("");
  const [tax, setTax] = useState("");
  const [creditAccount, setCreditAccount] = useState("");
  const [varianceAccount, setVarianceAccount] = useState("");
  const listing = useQuery({
    queryKey: ["inventory-returns", search, page],
    queryFn: async () =>
      (
        await api.get<{ items: ReturnDocument[]; total_pages: number }>(
          "/inventory/returns",
          { params: { search, page } },
        )
      ).data,
  });
  const detail = useQuery({
    queryKey: ["inventory-return", id],
    queryFn: async () =>
      (await api.get<ReturnDocument>(`/inventory/returns/${id}`)).data,
    enabled: !!id,
  });
  const sources = useQuery({
    queryKey: ["inventory-return-sources", sourceSearch, sourcePage],
    queryFn: async () =>
      (
        await api.get<{
          items: Array<{ id: number; number: string; supplier: string }>;
          total_pages: number;
        }>("/inventory/returns/sources", {
          params: { search: sourceSearch, page: sourcePage },
        })
      ).data,
    enabled: creating,
  });
  const sourceId = creating ? Number(receiptId) : detail.data?.goods_receipt_id;
  const source = useQuery({
    queryKey: ["inventory-return-source", sourceId],
    queryFn: async () =>
      (await api.get<Source>(`/inventory/returns/sources/${sourceId}`)).data,
    enabled: !!sourceId,
  });
  const accounts = useQuery({
    queryKey: ["inventory-return-accounts"],
    queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }),
    enabled: creating || !!id,
  });
  useEffect(() => {
    setReplacementQty({});
    setInvoiceId("");
    setCreditRef("");
    setNet("");
    setTax("");
    setCreditAccount("");
    setVarianceAccount("");
    setDeliveryNote("");
  }, [id]);
  const action = useMutation({
    mutationFn: async ({ path, data }: { path: string; data?: unknown }) =>
      (await api.post<ReturnDocument>(path, data)).data,
    onSuccess: async (row) => {
      setCreating(false);
      setParams({ id: String(row.id) });
      setReplacementQty({});
      setDeliveryNote("");
      await Promise.all([
        client.invalidateQueries({ queryKey: ["inventory-return"] }),
        client.invalidateQueries({ queryKey: ["inventory-returns"] }),
        client.invalidateQueries({ queryKey: ["inventory-return-source"] }),
        client.invalidateQueries({ queryKey: ["inventory"] }),
        client.invalidateQueries({ queryKey: ["inventory-period-report"] }),
        ...[
          "inventory-credit-invoices",
          "supplier-invoices",
          "supplier-invoice",
          "supplier-adjustments",
          "payments-ready-to-pay",
          "eligible-payment-invoices",
          "accounts-payable-aging",
          "general-ledger",
          "journal-entries",
          "trial-balance",
          "goods-receipts",
          "stock-movements",
        ].map((key) => client.invalidateQueries({ queryKey: [key] })),
      ]);
    },
  });
  const chooseAccount = (
    value: string,
    onChange: (value: string) => void,
    kind = "ASSET",
  ) => (
    <select
      aria-label={
        kind === "ASSET"
          ? "Supplier return asset account"
          : "Return variance expense account"
      }
      className={input}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">Select account</option>
      {accounts.data
        ?.filter((a) => a.account_type === kind)
        .map((a) => (
          <option value={a.id} key={a.id}>
            {a.account_code} — {a.account_name}
          </option>
        ))}
    </select>
  );
  const row = detail.data;
  const error = action.error as {
    response?: { data?: { detail?: unknown } };
    message?: string;
  } | null;
  return (
    <div className="space-y-3">
      <PageHeader
        title="Supplier Returns"
        description="Partial warehouse returns linked to Receiving."
        actions={
          can("receiving.return") ? (
            <Button
              onClick={() => {
                setRequestKey(crypto.randomUUID());
                setCreating(true);
                setReceiptId("");
                setQuantities({});
                setReason("");
                action.reset();
              }}
            >
              Create Return
            </Button>
          ) : undefined
        }
      />
      {(error || listing.isError || detail.isError || source.isError) && (
        <p
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800"
        >
          {error
            ? String(error.response?.data?.detail ?? error.message)
            : "Unable to load return/source data. Refresh and retry."}
        </p>
      )}
      {creating && (
        <Card className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">New return draft</h2>
            <Button variant="outline" onClick={() => setCreating(false)}>
              Cancel
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <label className={label}>
              Find Receiving
              <input
                className={input}
                value={sourceSearch}
                onChange={(e) => {
                  setSourceSearch(e.target.value);
                  setSourcePage(1);
                }}
                placeholder="GR number"
              />
            </label>
            <label className={`${label} md:col-span-2`}>
              Original Receiving
              <select
                className={input}
                value={receiptId}
                onChange={(e) => {
                  setReceiptId(e.target.value);
                  setQuantities({});
                }}
              >
                <option value="">Select Receiving</option>
                {sources.data?.items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.number} — {s.supplier}
                  </option>
                ))}
              </select>
            </label>
            <label className={label}>
              Return date
              <input
                type="date"
                className={input}
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <label className={label}>
              Purpose
              <select
                className={input}
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              >
                <option value="REPLACEMENT">Replacement goods</option>
                <option value="AP_CREDIT">
                  Reduce payable / supplier credit
                </option>
              </select>
            </label>
            <label className={label}>
              Supplier return clearing asset
              {chooseAccount(clearing, setClearing)}
            </label>
          </div>
          {(sources.data?.total_pages ?? 0) > 1 && (
            <div className="flex items-center gap-2 text-xs">
              <Button
                variant="outline"
                disabled={sourcePage === 1}
                onClick={() => setSourcePage((p) => p - 1)}
              >
                Previous receipts
              </Button>
              <span>
                {sourcePage} / {sources.data?.total_pages}
              </span>
              <Button
                variant="outline"
                disabled={sourcePage >= (sources.data?.total_pages ?? 1)}
                onClick={() => setSourcePage((p) => p + 1)}
              >
                Next receipts
              </Button>
            </div>
          )}
          <label className={label}>
            Reason
            <input
              className={input}
              value={reason}
              maxLength={1000}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-2">Item</th>
                  <th>UOM</th>
                  <th>Received</th>
                  <th>Returned</th>
                  <th>Remaining</th>
                  <th>Stock</th>
                  <th className="w-28">Return now</th>
                </tr>
              </thead>
              <tbody>
                {source.data?.items.map((line) => (
                  <tr className="border-b" key={line.id}>
                    <td className="p-2">
                      <strong>{line.code}</strong> — {line.name}
                    </td>
                    <td>{line.uom}</td>
                    {[
                      line.received,
                      line.returned,
                      line.remaining,
                      line.available,
                    ].map((v, i) => (
                      <td key={i}>{quantity(v)}</td>
                    ))}
                    <td>
                      <input
                        aria-label={`Return quantity ${line.code}`}
                        className={input}
                        type="number"
                        min="0"
                        step="0.01"
                        max={Math.min(
                          Number(line.remaining),
                          Number(line.available),
                        )}
                        value={quantities[line.id] ?? ""}
                        onChange={(e) =>
                          setQuantities((q) => ({
                            ...q,
                            [line.id]: e.target.value,
                          }))
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-right">
            <Button
              disabled={
                action.isPending ||
                !receiptId ||
                !date ||
                !reason.trim() ||
                !clearing ||
                !Object.values(quantities).some((q) => Number(q) > 0)
              }
              onClick={() =>
                action.mutate({
                  path: "/inventory/returns",
                  data: {
                    request_key: requestKey,
                    goods_receipt_id: Number(receiptId),
                    purpose,
                    return_date: date,
                    reason,
                    clearing_account_id: Number(clearing),
                    items: Object.entries(quantities)
                      .filter(([, q]) => Number(q) > 0)
                      .map(([line, q]) => ({
                        goods_receipt_item_id: Number(line),
                        quantity: Number(q),
                      })),
                  },
                })
              }
            >
              Save Draft
            </Button>
          </div>
        </Card>
      )}
      {!creating && row && (
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="font-semibold">
                {row.number} · {row.status}
              </h2>
              <p className="text-xs text-slate-500">
                {row.supplier_name} · {row.return_date} ·{" "}
                {row.purpose === "REPLACEMENT"
                  ? "Replacement"
                  : "Supplier credit"}{" "}
                ·{" "}
                <Link
                  className="text-emerald-700 underline"
                  to={`/receiving/${row.goods_receipt_id}`}
                >
                  {row.receipt_number}
                </Link>
              </p>
            </div>
            {row.status === "DRAFT" && can("receiving.return") && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={action.isPending}
                  onClick={() =>
                    action.mutate({ path: `/inventory/returns/${row.id}/void` })
                  }
                >
                  Void Draft
                </Button>
                <Button
                  disabled={action.isPending}
                  onClick={() =>
                    action.mutate({ path: `/inventory/returns/${row.id}/post` })
                  }
                >
                  Post Return
                </Button>
              </div>
            )}
          </div>
          <p className="text-sm">{row.reason}</p>
          {(can("finance.view") || can("finance.manage")) && (
            <div className="flex gap-3 text-xs text-emerald-700">
              {row.journal_entry_id && (
                <Link
                  className="underline"
                  to={`/journal-entries/${row.journal_entry_id}`}
                >
                  Return journal
                </Link>
              )}
              {row.credit_journal_id && (
                <Link
                  className="underline"
                  to={`/journal-entries/${row.credit_journal_id}`}
                >
                  Supplier credit journal
                </Link>
              )}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-2">Item</th>
                  <th>UOM</th>
                  <th>Returned</th>
                  <th>Carrying value</th>
                  <th>Replaced</th>
                </tr>
              </thead>
              <tbody>
                {row.items.map((line) => (
                  <tr key={line.id} className="border-b">
                    <td className="p-2">
                      <Link
                        className="text-emerald-700"
                        to={`/inventory/movements?product_id=${line.product_id}&warehouse_id=${row.warehouse_id}`}
                      >
                        {line.code}
                      </Link>{" "}
                      — {line.name}
                    </td>
                    <td>{line.uom}</td>
                    <td>{quantity(line.quantity)}</td>
                    <td>{money(line.line_cost)}</td>
                    <td>{quantity(line.replaced_quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-right text-sm">
            Total carrying value: <strong>{money(row.total_cost)}</strong> ·
            Clearing balance: <strong>{money(row.clearing_balance)}</strong>
          </div>
          {row.status === "POSTED" &&
            row.purpose === "REPLACEMENT" &&
            can("receiving.post") &&
            row.items.some(
              (line) => Number(line.replaced_quantity) < Number(line.quantity),
            ) && (
              <div className="space-y-3 border-t pt-3">
                <h3 className="text-sm font-semibold">
                  Receive replacement goods
                </h3>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className={label}>
                    Receiving date
                    <input
                      type="date"
                      className={input}
                      value={replacementDate}
                      onChange={(e) => setReplacementDate(e.target.value)}
                    />
                  </label>
                  <label className={label}>
                    Delivery note
                    <input
                      className={input}
                      value={deliveryNote}
                      onChange={(e) => setDeliveryNote(e.target.value)}
                    />
                  </label>
                </div>
                {row.items
                  .filter(
                    (line) =>
                      Number(line.replaced_quantity) < Number(line.quantity),
                  )
                  .map((line) => (
                    <label
                      key={line.id}
                      className="flex items-center justify-between gap-3 text-xs"
                    >
                      <span>
                        {line.code} — {line.name} · remaining{" "}
                        {quantity(
                          Number(line.quantity) -
                            Number(line.replaced_quantity),
                        )}{" "}
                        {line.uom}
                      </span>
                      <input
                        className={`${input} max-w-28`}
                        aria-label={`Replacement quantity ${line.code}`}
                        type="number"
                        min="0"
                        step="0.01"
                        max={
                          Number(line.quantity) - Number(line.replaced_quantity)
                        }
                        value={replacementQty[line.id] ?? ""}
                        onChange={(e) =>
                          setReplacementQty((q) => ({
                            ...q,
                            [line.id]: e.target.value,
                          }))
                        }
                      />
                    </label>
                  ))}
                <Button
                  disabled={
                    action.isPending ||
                    !deliveryNote.trim() ||
                    !Object.values(replacementQty).some((q) => Number(q) > 0)
                  }
                  onClick={() =>
                    action.mutate({
                      path: `/inventory/returns/${row.id}/replacement`,
                      data: {
                        received_date: replacementDate,
                        delivery_note: deliveryNote,
                        items: Object.entries(replacementQty)
                          .filter(([, q]) => Number(q) > 0)
                          .map(([line, q]) => ({
                            return_item_id: Number(line),
                            quantity: Number(q),
                          })),
                      },
                    })
                  }
                >
                  Post Replacement Receiving
                </Button>
              </div>
            )}
          {row.replacement_receipts.map((r) => (
            <div key={r.id} className="text-xs">
              Replacement Receiving:{" "}
              <Link
                className="text-emerald-700 underline"
                to={`/receiving/${r.id}`}
              >
                {r.number}
              </Link>
            </div>
          ))}
          {row.status === "POSTED" &&
            row.purpose === "AP_CREDIT" &&
            !row.credit_journal_id &&
            can("finance.manage") && (
              <div className="space-y-3 border-t pt-3">
                <h3 className="text-sm font-semibold">
                  Supplier credit — Finance
                </h3>
                <div className="grid gap-3 md:grid-cols-3">
                  <label className={label}>
                    Original supplier invoice
                    <select
                      className={input}
                      value={invoiceId}
                      onChange={(e) => setInvoiceId(e.target.value)}
                    >
                      <option value="">Select invoice</option>
                      {source.data?.invoices.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.number} · {i.status} · due {money(i.balance)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className={label}>
                    Credit date
                    <input
                      type="date"
                      className={input}
                      value={creditDate}
                      onChange={(e) => setCreditDate(e.target.value)}
                    />
                  </label>
                  <label className={label}>
                    Supplier credit reference
                    <input
                      className={input}
                      value={creditRef}
                      onChange={(e) => setCreditRef(e.target.value)}
                    />
                  </label>
                  <label className={label}>
                    Credit base amount
                    <input
                      className={input}
                      type="number"
                      min="0"
                      step="0.01"
                      value={net}
                      onChange={(e) => setNet(e.target.value)}
                    />
                  </label>
                  <label className={label}>
                    PPN credit (supplier document)
                    <input
                      className={input}
                      type="number"
                      min="0"
                      step="0.01"
                      value={tax}
                      onChange={(e) => setTax(e.target.value)}
                    />
                  </label>
                  <label className={label}>
                    Excess supplier credit asset
                    {chooseAccount(creditAccount, setCreditAccount)}
                  </label>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="text-sm">
                    Credit base − carrying value:{" "}
                    <strong>
                      {money(Number(net) - Number(row.total_cost))}
                    </strong>
                  </div>
                  {Number(net) !== Number(row.total_cost) && (
                    <label className={label}>
                      Explicit variance expense account
                      {chooseAccount(
                        varianceAccount,
                        setVarianceAccount,
                        "EXPENSE",
                      )}
                    </label>
                  )}
                </div>
                <Button
                  disabled={
                    action.isPending ||
                    !invoiceId ||
                    !creditRef.trim() ||
                    net === "" ||
                    (Number(net) !== Number(row.total_cost) && !varianceAccount)
                  }
                  onClick={() =>
                    action.mutate({
                      path: `/inventory/returns/${row.id}/credit`,
                      data: {
                        supplier_invoice_id: Number(invoiceId),
                        credit_date: creditDate,
                        credit_reference: creditRef,
                        net_amount: Number(net),
                        tax_amount: Number(tax || 0),
                        supplier_credit_account_id:
                          Number(creditAccount) || null,
                        variance_account_id: Number(varianceAccount) || null,
                      },
                    })
                  }
                >
                  Post Supplier Credit
                </Button>
              </div>
            )}
          {row.credit_journal_id && (
            <div className="border-t pt-3 text-sm">
              Supplier credit {row.credit_reference} · AP reduced:{" "}
              <strong>{money(row.credit_applied)}</strong> · Separate supplier
              credit: <strong>{money(row.supplier_credit)}</strong>
            </div>
          )}
          <ReturnCompletion
            key={`${row.id}-${row.events?.length ?? 0}`}
            id={row.id}
            status={row.status}
            balance={Number(row.remaining_supplier_credit ?? 0)}
            history={row.events ?? []}
            canManage={can("finance.manage")}
            pending={action.isPending}
            accounts={accounts.data ?? []}
            submit={(value) => action.mutate(value)}
          />
        </Card>
      )}
      <Card className="overflow-hidden">
        <div className="border-b p-3">
          <input
            aria-label="Search returns"
            className={input}
            placeholder="Return or Receiving number"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left">
                <th className="p-3">Return</th>
                <th>Date</th>
                <th>Supplier</th>
                <th>Receiving</th>
                <th>Purpose</th>
                <th>Value</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {listing.data?.items.map((r) => (
                <tr key={r.id} className="border-b">
                  <td className="p-3">
                    <button
                      className="font-medium text-emerald-700 underline"
                      onClick={() => {
                        setCreating(false);
                        setParams({ id: String(r.id) });
                        action.reset();
                      }}
                    >
                      {r.number}
                    </button>
                  </td>
                  <td>{r.return_date}</td>
                  <td>{r.supplier_name}</td>
                  <td>{r.receipt_number}</td>
                  <td>
                    {r.purpose === "REPLACEMENT"
                      ? "Replacement"
                      : "Supplier credit"}
                  </td>
                  <td>{money(r.total_cost)}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-end gap-3 p-3 text-xs">
          <Button
            variant="outline"
            disabled={page === 1 || listing.isFetching}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span>
            {page} / {Math.max(1, listing.data?.total_pages ?? 1)}
          </span>
          <Button
            variant="outline"
            disabled={
              page >= (listing.data?.total_pages ?? 1) || listing.isFetching
            }
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </Card>
    </div>
  );
}

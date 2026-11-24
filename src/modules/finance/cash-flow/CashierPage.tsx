import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Pencil, Plus } from "lucide-react";
import api from "@/api/client";
import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import {
  collectReportPages,
  type InventoryPrintReport,
  type ReportPage,
} from "@/utils/inventoryPrint";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Pagination from "@/components/datatable/Pagination";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card, { CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";
import SearchableSelect from "@/components/form/SearchableSelect";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { FORM_UI } from "@/config/formUi";
import { listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import type { AccountLookup } from "@/modules/master/chart-of-accounts/types";
import useFormRecovery from "@/hooks/useFormRecovery";
import useAuthStore from "@/store/auth";
import { todayLocal } from "@/utils/dateConstraints";

type Journal = {
  id: number;
  journal_number: string;
  document_type: string;
  posting_date: string;
  description: string;
  total_debit: string;
  status: string;
};

type CashSummary = {
  account_id: number;
  account_name: string;
  account_subtype: string;
  opening_balance: string;
  total_inflow: string;
  total_outflow: string;
  closing_balance: string;
};

type Entry = {
  posting_date: string;
  operation: string;
  cash_account_id: number;
  counterpart_account_id: number;
  amount: number;
  location_id: number;
  department_id: number | null;
  business_unit_id: number | null;
  reference_number: string;
  description: string;
};

type FormErrors = Partial<Record<keyof Entry, string>>;

const PAGE_SIZE = 50;
const CASH_TYPES = ["BANK", "CASH", "PETTY_CASH"];

const EVENT_LABELS: Record<string, string> = {
  PAYMENT: "Expense payment",
  REPLENISHMENT: "Replenishment",
  TRANSFER: "Transfer out",
  RECEIPT: "Cash receipt",
};

const OPERATION_HELP: Record<string, string> = {
  PAYMENT: "Petty cash → expense. Use this for small costs paid from the float.",
  REPLENISHMENT: "Bank or cash → petty cash. Use this to top up the float.",
  TRANSFER: "Petty cash → cash or bank. Use this to return or move funds out.",
  RECEIPT:
    "Legacy cash receipt. New petty cash entries use replenishment, expense payment, or transfer out.",
};

const blank = (): Entry => ({
  posting_date: todayLocal(),
  operation: "PAYMENT",
  cash_account_id: 0,
  counterpart_account_id: 0,
  amount: 0,
  location_id: 0,
  department_id: null,
  business_unit_id: null,
  reference_number: "",
  description: "",
});

const isValidEntry = (value: unknown): value is Entry =>
  !!value &&
  typeof value === "object" &&
  typeof (value as Entry).posting_date === "string" &&
  typeof (value as Entry).amount === "number";

const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const titleCase = (value: string) =>
  value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());

const eventLabel = (documentType: string) => {
  const operation = documentType.replace("CASHIER_", "");
  return EVENT_LABELS[operation] ?? titleCase(operation);
};

const statusLabel = (status: string) =>
  ({ POSTED: "Posted", DRAFT: "Draft", VOID: "Voided", VOIDED: "Voided" }[status] ?? titleCase(status));

const statusVariant = (status: string): BadgeVariant => {
  if (status === "POSTED") return "success";
  if (status === "DRAFT") return "warning";
  if (status === "VOID" || status === "VOIDED") return "danger";
  return "default";
};

const currentMonth = () => {
  const today = todayLocal();
  return { from: `${today.slice(0, 7)}-01`, to: today };
};

export default function CashierPage() {
  const canManage = useAuthStore((state) => state.hasPermission("finance.manage"));
  const queryClient = useQueryClient();
  const initialPeriod = useMemo(currentMonth, []);
  const [dateFrom, setDateFrom] = useState(initialPeriod.from);
  const [dateTo, setDateTo] = useState(initialPeriod.to);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<Entry>(blank);
  const [errors, setErrors] = useState<FormErrors>({});

  const period = `${dateFrom} → ${dateTo}`;
  const invalidPeriod = dateFrom > dateTo;

  const createRecovery = useFormRecovery("petty-cash:create", form, open && editingId === null, isValidEntry);
  const editRecovery = useFormRecovery(
    `petty-cash:edit:${editingId ?? "none"}`,
    form,
    open && editingId !== null,
    isValidEntry,
  );
  const recovery = editingId === null ? createRecovery : editRecovery;

  const entries = useQuery({
    queryKey: ["cashier", dateFrom, dateTo, page],
    enabled: !invalidPeriod,
    queryFn: async () =>
      (
        await api.get<{
          items: Journal[];
          total_items: number;
          total_pages: number;
          page: number;
          page_size: number;
        }>("/cashier", {
          params: {
            date_from: dateFrom,
            date_to: dateTo,
            page,
            page_size: PAGE_SIZE,
            petty_cash: true,
          },
        })
      ).data,
  });

  const balances = useQuery({
    queryKey: ["cashier-balances", dateFrom, dateTo],
    enabled: !invalidPeriod,
    queryFn: async () =>
      (await api.get<CashSummary[]>("/cash-flow/accounts", { params: { date_from: dateFrom, date_to: dateTo } })).data,
  });

  const accounts = useQuery({
    queryKey: ["cashier-accounts"],
    enabled: open,
    queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }),
  });
  const locations = useQuery({
    queryKey: ["cashier-locations"],
    enabled: open,
    queryFn: () => listLocations({ is_active: true }),
  });
  const departments = useQuery({
    queryKey: ["cashier-departments", form.location_id],
    enabled: open && !!form.location_id,
    queryFn: () => listDepartments({ location_id: form.location_id, is_active: true }),
  });

  const refresh = () => {
    ["cashier", "cashier-balances", "journal-entries", "general-ledger", "management-dashboard", "financial-report-comparison"].forEach(
      (key) => queryClient.invalidateQueries({ queryKey: [key] }),
    );
  };

  const save = useMutation({
    mutationFn: async () =>
      editingId === null
        ? (await api.post("/cashier", form)).data
        : (await api.patch(`/cashier/${editingId}`, form)).data,
    onSuccess: () => {
      recovery.clear();
      setErrors({});
      setOpen(false);
      setForm(blank());
      setEditingId(null);
      refresh();
      toast.success(editingId === null ? "Petty cash draft saved" : "Petty cash draft updated");
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || "Petty cash entry could not be saved"),
  });

  const action = useMutation({
    mutationFn: ({ id, name }: { id: number; name: "post" | "void" }) => api.post(`/cashier/${id}/${name}`),
    onSuccess: (_data, variables) => {
      refresh();
      toast.success(variables.name === "post" ? "Petty cash entry posted" : "Petty cash draft voided");
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || "Petty cash action failed"),
  });

  const loadReport = async (): Promise<InventoryPrintReport> => {
    const [book, cash] = await Promise.all([
      collectReportPages<Journal>(async (pageNumber) =>
        (
          await api.get<ReportPage<Journal>>("/cashier", {
            params: {
              date_from: dateFrom,
              date_to: dateTo,
              page: pageNumber,
              page_size: 100,
              petty_cash: true,
            },
          })
        ).data,
      ),
      api.get<CashSummary[]>("/cash-flow/accounts", { params: { date_from: dateFrom, date_to: dateTo } }),
    ]);
    return {
      title: "Petty Cash Book",
      context: period,
      rowCount: book.items.length,
      columns: [
        { label: "Number" },
        { label: "Date" },
        { label: "Event" },
        { label: "Reference / description" },
        { label: "Amount", numeric: true },
        { label: "Status" },
      ],
      groups: [
        {
          title: "Petty cash entries",
          rows: book.items.map((item) => [
            item.journal_number,
            item.posting_date,
            eventLabel(item.document_type),
            item.description,
            money(item.total_debit),
            statusLabel(item.status),
          ]),
        },
        ...cash.data
          .filter((account) => account.account_subtype === "PETTY_CASH")
          .map((account) => ({
            title: account.account_name,
            rows: [
              ["Opening", null, null, null, money(account.opening_balance), null],
              ["In", null, null, null, money(account.total_inflow), null],
              ["Out", null, null, null, money(account.total_outflow), null],
              ["Closing", null, null, null, money(account.closing_balance), null],
            ],
          })),
      ],
    };
  };

  const allAccounts = accounts.data ?? [];
  const cashAccounts = allAccounts.filter(
    (account) => account.account_type === "ASSET" && account.account_subtype === "PETTY_CASH",
  );
  const counterpartAccounts = allAccounts.filter((account) => {
    if (account.id === form.cash_account_id) return false;
    if (form.operation === "PAYMENT") {
      return account.account_type === "EXPENSE" && account.normal_balance === "DEBIT";
    }
    if (form.operation === "RECEIPT") {
      return ["REVENUE", "INCOME"].includes(account.account_type) && account.normal_balance === "CREDIT";
    }
    return account.account_type === "ASSET" && CASH_TYPES.includes(account.account_subtype);
  });

  const accountOptions = (values: AccountLookup[]) =>
    values.map((account) => ({
      id: account.id,
      label: `${account.account_code} — ${account.account_name}`,
      keywords: [account.account_code, account.account_name],
    }));

  const summary = useMemo(
    () => (balances.data ?? []).filter((account) => account.account_subtype === "PETTY_CASH"),
    [balances.data],
  );
  const totals = summary.reduce(
    (result, account) => ({
      opening: result.opening + Number(account.opening_balance || 0),
      inflow: result.inflow + Number(account.total_inflow || 0),
      outflow: result.outflow + Number(account.total_outflow || 0),
      closing: result.closing + Number(account.closing_balance || 0),
    }),
    { opening: 0, inflow: 0, outflow: 0, closing: 0 },
  );
  const entryCount = entries.data?.total_items ?? 0;
  const rows = entries.data?.items ?? [];

  const setField = <K extends keyof Entry>(field: K, value: Entry[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const setOperation = (operation: string) => {
    setForm((current) => ({ ...current, operation, counterpart_account_id: 0 }));
    setErrors((current) => ({ ...current, operation: undefined, counterpart_account_id: undefined }));
  };

  const openCreate = () => {
    setEditingId(null);
    setErrors({});
    const saved = createRecovery.load();
    setForm(saved && isValidEntry(saved) ? saved : blank());
    if (saved) createRecovery.notifyRestored();
    setOpen(true);
  };

  const openEdit = async (id: number) => {
    if (editingId === id) {
      setOpen(true);
      return;
    }
    try {
      const response = await api.get<{ entry: Entry }>(`/cashier/${id}`);
      setErrors({});
      setForm({ ...blank(), ...response.data.entry, amount: Number(response.data.entry.amount) });
      setEditingId(id);
      setOpen(true);
    } catch {
      toast.error("Could not load the petty cash draft");
    }
  };

  const submit = () => {
    const nextErrors: FormErrors = {};
    if (!form.posting_date) nextErrors.posting_date = "Choose the business date.";
    if (!form.location_id) nextErrors.location_id = "Choose a location.";
    if (!form.cash_account_id) nextErrors.cash_account_id = "Choose the petty cash account.";
    if (!form.counterpart_account_id) nextErrors.counterpart_account_id = "Choose the counterpart account.";
    if (!(form.amount > 0)) nextErrors.amount = "Enter an amount greater than zero.";
    if (!form.reference_number.trim()) nextErrors.reference_number = "Enter the supporting document reference.";
    if (!form.description.trim()) nextErrors.description = "Enter a short description.";
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    save.mutate();
  };

  const inputClass = `${FORM_UI.controlBase} ${FORM_UI.density.compact.control}`;

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="print-document space-y-2">
        <PageHeader
          title="Petty Cash"
          description="Record petty cash movements and review the float by period."
          actions={
            <>
              <Input
                aria-label="From date"
                type="date"
                value={dateFrom}
                onChange={(event) => {
                  setDateFrom(event.target.value);
                  setPage(1);
                }}
              />
              <Input
                aria-label="To date"
                type="date"
                value={dateTo}
                onChange={(event) => {
                  setDateTo(event.target.value);
                  setPage(1);
                }}
              />
              <InventoryPrintButton loadReport={loadReport} reportLabel="Petty cash" disabled={invalidPeriod} />
              {canManage && (
                <Button size="sm" aria-label="Create petty cash entry" onClick={openCreate}>
                  <Plus size={15} /> New entry
                </Button>
              )}
            </>
          }
        >
          <div className="mt-0.5 text-[11px] text-slate-500">{period}</div>
        </PageHeader>

        {invalidPeriod && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            From date must be on or before To date.
          </div>
        )}

        <ModuleSummary
          metrics={[
            { label: "Petty accounts", value: summary.length },
            { label: "Opening", value: money(totals.opening) },
            { label: "In", value: money(totals.inflow) },
            { label: "Out", value: money(totals.outflow) },
            { label: "Closing", value: money(totals.closing), note: "Across petty cash accounts in this period" },
            { label: "Entries", value: entryCount },
          ]}
        />

        <Card className="overflow-hidden p-0">
          <CardHeader>
            <div>
              <CardTitle className="text-sm">Petty cash accounts</CardTitle>
              <CardDescription>Balances include posted entries and complete drafts in open periods.</CardDescription>
            </div>
          </CardHeader>
          {invalidPeriod ? (
            <div className="m-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              Set a valid date range to load petty cash balances.
            </div>
          ) : balances.isError ? (
            <div role="alert" className="m-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div className="font-semibold">Petty cash balances could not be loaded.</div>
              <Button className="mt-2" size="sm" variant="outline" onClick={() => balances.refetch()}>
                Try again
              </Button>
            </div>
          ) : (
            <Table containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
              <THead>
                <TR>
                  <TH>Cash account</TH>
                  <TH numeric>Opening</TH>
                  <TH numeric>In</TH>
                  <TH numeric>Out</TH>
                  <TH numeric>Closing</TH>
                </TR>
              </THead>
              <TBody>
                {summary.map((account) => (
                  <TR key={account.account_id}>
                    <TD>
                      <Link
                        className="font-medium text-emerald-700 hover:underline"
                        to={`/cash-accounts/${account.account_id}?date_from=${dateFrom}&date_to=${dateTo}`}
                      >
                        {account.account_name}
                      </Link>
                    </TD>
                    <TD numeric>{money(account.opening_balance)}</TD>
                    <TD numeric>{money(account.total_inflow)}</TD>
                    <TD numeric>{money(account.total_outflow)}</TD>
                    <TD numeric className="font-semibold tabular-nums">
                      {money(account.closing_balance)}
                    </TD>
                  </TR>
                ))}
                {!summary.length && (
                  <TR>
                    <TD colSpan={5} className="p-6 text-center text-slate-500">
                      No active petty cash account is available for this period.
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          )}
        </Card>

        <Card className="overflow-hidden p-0">
          <CardHeader>
            <div>
              <CardTitle className="text-sm">Petty cash entries</CardTitle>
              <CardDescription>Replenishments, expense payments, and transfers in the selected period.</CardDescription>
            </div>
            <Badge variant="outline">{entryCount} total</Badge>
          </CardHeader>
          {invalidPeriod ? (
            <div className="m-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              Set a valid date range to load petty cash entries.
            </div>
          ) : entries.isError ? (
            <div role="alert" className="m-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div className="font-semibold">Petty cash entries could not be loaded.</div>
              <Button className="mt-2" size="sm" variant="outline" onClick={() => entries.refetch()}>
                Try again
              </Button>
            </div>
          ) : entries.isPending ? (
            <Loading message="Loading petty cash entries..." />
          ) : (
            <>
              <Table containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                <THead>
                  <TR>
                    <TH>Number</TH>
                    <TH>Date</TH>
                    <TH>Event</TH>
                    <TH>Reference / description</TH>
                    <TH numeric>Amount</TH>
                    <TH>Status</TH>
                    <TH numeric>Actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {rows.map((entry) => (
                    <TR key={entry.id}>
                      <TD>
                        <TableCellStack
                          primary={
                            <Link className="font-medium text-emerald-700 hover:underline" to={`/journal-entries/${entry.id}`}>
                              {entry.journal_number}
                            </Link>
                          }
                        />
                      </TD>
                      <TD>{entry.posting_date}</TD>
                      <TD>
                        <Badge variant="outline">{eventLabel(entry.document_type)}</Badge>
                      </TD>
                      <TD className="max-w-md truncate" title={entry.description}>
                        {entry.description}
                      </TD>
                      <TD numeric className="font-semibold tabular-nums">
                        {money(entry.total_debit)}
                      </TD>
                      <TD>
                        <Badge variant={statusVariant(entry.status)}>{statusLabel(entry.status)}</Badge>
                      </TD>
                      <TD>
                        <div className="flex justify-end gap-1 print:hidden">
                          {canManage && entry.status === "DRAFT" && (
                            <Button
                              size="xs"
                              variant="outline"
                              title="Edit draft"
                              aria-label={`Edit ${entry.journal_number}`}
                              onClick={() => openEdit(entry.id)}
                            >
                              <Pencil size={13} />
                            </Button>
                          )}
                          {canManage &&
                            entry.status === "DRAFT" &&
                            (["post", "void"] as const).map((name) => (
                              <Button
                                key={name}
                                size="xs"
                                variant="outline"
                                disabled={action.isPending}
                                onClick={() => {
                                  const message = name === "post" ? "Post this petty cash entry?" : "Void this draft?";
                                  if (window.confirm(message)) action.mutate({ id: entry.id, name });
                                }}
                              >
                                {name === "post" ? "Post" : "Void"}
                              </Button>
                            ))}
                          <Link
                            className="inline-flex h-7 items-center rounded border border-slate-200 px-2 text-xs text-slate-700 hover:bg-slate-50"
                            to={`/journal-entries/${entry.id}/print`}
                          >
                            Print
                          </Link>
                        </div>
                      </TD>
                    </TR>
                  ))}
                  {!rows.length && (
                    <TR>
                      <TD colSpan={7} className="p-10 text-center text-slate-500">
                        <div className="font-medium">No petty cash entries in this period.</div>
                        <div className="mt-1 text-xs">Choose another date range or record a new entry.</div>
                      </TD>
                    </TR>
                  )}
                </TBody>
              </Table>
              <div className="px-3">
                <Pagination
                  page={page}
                  pages={entries.data?.total_pages ?? 1}
                  total={entryCount}
                  pageSize={PAGE_SIZE}
                  noun="entries"
                  onChange={setPage}
                />
              </div>
            </>
          )}
        </Card>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingId === null ? "Record petty cash" : "Edit petty cash entry"}</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <div className={FORM_UI.section}>
                <div className="space-y-3">
                  <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900">
                    {OPERATION_HELP[form.operation] ?? "Choose a transaction type."}
                  </div>
                  <div className={FORM_UI.grid}>
                    <label className="text-xs font-medium text-slate-700">
                      Business date
                      <Input
                        className="mt-1"
                        type="date"
                        error={!!errors.posting_date}
                        value={form.posting_date}
                        onChange={(event) => setField("posting_date", event.target.value)}
                      />
                      {errors.posting_date && <span className={FORM_UI.errorText}>{errors.posting_date}</span>}
                      <span className={FORM_UI.helpText}>Closed periods are rejected when saving.</span>
                    </label>
                    <label className="text-xs font-medium text-slate-700">
                      Transaction type
                      <select
                        className={`${inputClass} mt-1`}
                        value={form.operation}
                        onChange={(event) => setOperation(event.target.value)}
                      >
                        <option value="PAYMENT">Expense payment</option>
                        <option value="REPLENISHMENT">Replenishment / transfer in</option>
                        <option value="TRANSFER">Cash / bank transfer out</option>
                        {form.operation === "RECEIPT" && <option value="RECEIPT">Legacy cash receipt</option>}
                      </select>
                    </label>

                    <div>
                      <SearchableSelect
                        label="Petty cash account"
                        required
                        dataField="cash_account_id"
                        invalid={!!errors.cash_account_id}
                        options={accountOptions(cashAccounts)}
                        value={form.cash_account_id || undefined}
                        onChange={(value) => setField("cash_account_id", value ?? 0)}
                      />
                      {errors.cash_account_id && <span className={FORM_UI.errorText}>{errors.cash_account_id}</span>}
                    </div>
                    <div>
                      <SearchableSelect
                        label={
                          form.operation === "PAYMENT"
                            ? "Expense account"
                            : form.operation === "REPLENISHMENT"
                              ? "Funding cash / bank account"
                              : form.operation === "TRANSFER"
                                ? "Destination cash / bank account"
                                : "Revenue account"
                        }
                        required
                        dataField="counterpart_account_id"
                        invalid={!!errors.counterpart_account_id}
                        options={accountOptions(counterpartAccounts)}
                        value={form.counterpart_account_id || undefined}
                        onChange={(value) => setField("counterpart_account_id", value ?? 0)}
                      />
                      {errors.counterpart_account_id && (
                        <span className={FORM_UI.errorText}>{errors.counterpart_account_id}</span>
                      )}
                    </div>

                    <div>
                      <SearchableSelect
                        label="Location"
                        required
                        dataField="location_id"
                        invalid={!!errors.location_id}
                        options={(locations.data ?? []).map((location) => ({ id: location.id, label: location.name }))}
                        value={form.location_id || undefined}
                        onChange={(value) => {
                          setField("location_id", value ?? 0);
                          setField("department_id", null);
                          setField(
                            "business_unit_id",
                            locations.data?.find((location) => location.id === value)?.business_unit_id ?? null,
                          );
                        }}
                      />
                      {errors.location_id && <span className={FORM_UI.errorText}>{errors.location_id}</span>}
                    </div>
                    <div>
                      <SearchableSelect
                        label="Department"
                        options={(departments.data ?? []).map((department) => ({ id: department.id, label: department.name }))}
                        value={form.department_id || undefined}
                        onChange={(value) => setField("department_id", value ?? null)}
                      />
                    </div>

                    <div>
                      <label className="text-xs font-medium text-slate-700">Amount</label>
                      <CurrencyInput
                        value={form.amount}
                        invalid={!!errors.amount}
                        dataField="amount"
                        onValueChange={(value) => setField("amount", value)}
                      />
                      {errors.amount && <span className={FORM_UI.errorText}>{errors.amount}</span>}
                    </div>
                    <label className="text-xs font-medium text-slate-700">
                      Supporting document reference
                      <Input
                        className="mt-1"
                        maxLength={100}
                        error={!!errors.reference_number}
                        value={form.reference_number}
                        onChange={(event) => setField("reference_number", event.target.value)}
                      />
                      {errors.reference_number && <span className={FORM_UI.errorText}>{errors.reference_number}</span>}
                    </label>
                    <label className="text-xs font-medium text-slate-700 md:col-span-2">
                      Description
                      <Input
                        className="mt-1"
                        maxLength={500}
                        error={!!errors.description}
                        value={form.description}
                        onChange={(event) => setField("description", event.target.value)}
                      />
                      {errors.description && <span className={FORM_UI.errorText}>{errors.description}</span>}
                    </label>
                  </div>
                </div>
              </div>
            </DialogBody>
            <DialogFooter>
              <FormRecoveryActions
                failed={recovery.failed}
                onDiscard={() => {
                  recovery.clear();
                  setErrors({});
                  setForm(blank());
                  setEditingId(null);
                  setOpen(false);
                }}
              />
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button loading={save.isPending} onClick={submit}>
                Save draft
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DataWorkspace>
  );
}

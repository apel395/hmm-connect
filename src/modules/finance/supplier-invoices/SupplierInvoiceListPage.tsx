import { Printer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import ListToolbar from "@/components/common/ListToolbar";
import ModuleSummary from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import QuantityInput from "@/components/form/QuantityInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { getAccounts } from "@/modules/master/chart-of-accounts/api";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import purchaseOrderApi from "@/modules/purchasing/purchase-order/api/purchaseOrderApi";
import goodsReceiptApi from "@/modules/purchasing/goods-receipts/api/goodsReceiptApi";
import { createInvoice, getInvoice, InvoiceLine, listEligibleReceiptSources, listInvoices, updateInvoice } from "./api";
import { buildInvoicePayload, computeInvoiceTotals, withSyncedDocumentTotal } from "./totals";
import { invoiceErrorMessage, parseInvoiceError } from "./errors";
import { createVoucher, listEligibleInvoices } from "@/modules/finance/payment-vouchers/api";
import useAuthorization from "@/hooks/useAuthorization";
import useFormRecovery from "@/hooks/useFormRecovery";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";
import api from "@/api/client";

const today = () => new Date().toISOString().slice(0, 10);
const addDays = (value: string, days: number) => {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
};
const blankLine = (): InvoiceLine => ({ description: "", quantity: 0, uom: "", unit_price: 0, account_id: null, is_taxable: false, tax_rate: 0, tax_amount: 0 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const emptyForm = (): any => ({ supplier_id: 0, supplier_invoice_number: "", supplier_document_total: null, invoice_date: today(), received_date: today(), due_date: addDays(today(), 30), purchase_order_id: null, goods_receipt_id: null, business_unit_id: null, department_id: null, location_id: null, currency: "IDR", discount_amount: 0, withholding_tax_amount: 0, shipping_fee_amount: 0, admin_fee_amount: 0, other_fee_amount: 0, shipping_fee_account_id: null, admin_fee_account_id: null, other_fee_account_id: null, other_fee_description: "", supplier_document_url: "", tax_invoice_number: "", tax_invoice_date: "", notes: "", source_type: "LIVE", vat_decision:"", lines: [blankLine()] });
const validInvoiceInput = (v: unknown): v is ReturnType<typeof emptyForm> => { const x = v as any; return !!x && typeof x.invoice_date === "string" && typeof x.supplier_id === "number" && Array.isArray(x.lines); };
const withTaxSnapshot = (item: any, extra: Record<string, unknown> = {}): InvoiceLine => ({
  product_id: item.product_id,
  product_code: item.product_code,
  product_name: item.product_name,
  description: item.description || item.product_name,
  quantity: Number(item.quantity),
  uom: item.uom,
  unit_price: Number(item.unit_price ?? item.unit_cost ?? 0),
  is_taxable: Boolean(item.is_taxable),
  tax_rate: Number(item.tax_rate ?? 0),
  tax_amount: Number(item.tax_amount ?? 0),
  account_id: null,
  ...extra,
});

type AccountOption = {
  id: number;
  account_code?: string | null;
  account_name?: string | null;
  account_type?: string | null;
};

function AccountPicker({ value, selectedCode, selectedName, onChange }: { value: number | null | undefined; selectedCode?: string | null; selectedName?: string | null; onChange: (id: number | null) => void }) {
  const initialLabel = selectedCode || selectedName ? `${selectedCode ?? ""}${selectedCode && selectedName ? " — " : ""}${selectedName ?? ""}` : "";
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(initialLabel);
  const [debouncedQuery, setDebouncedQuery] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (value == null) {
      setQuery("");
      setDebouncedQuery("");
    }
  }, [value]);

  const lookup = useQuery({
    queryKey: ["coa-invoice-lookup", debouncedQuery],
    queryFn: async () => {
      const result = await getAccounts({
        page: 1,
        page_size: 50,
        search: debouncedQuery || undefined,
        is_active: true,
        is_posting: true,
        sort_by: "account_code",
        sort_order: "asc",
      });
      return result.items as AccountOption[];
    },
    enabled: open,
    staleTime: 30_000,
  });

  const accounts = lookup.data ?? [];
  const selectedFromLookup = accounts.find((account) => account.id === value);
  const selectedLabel = selectedFromLookup
    ? `${selectedFromLookup.account_code ?? ""} — ${selectedFromLookup.account_name ?? ""}`
    : initialLabel;
  const waitingForSearch = query.trim() !== debouncedQuery;

  const choose = (account: AccountOption) => {
    onChange(account.id);
    setQuery(`${account.account_code ?? ""} — ${account.account_name ?? ""}`);
    setOpen(false);
  };

  return <div className="relative">
    <input
      className={input}
      value={query}
      placeholder="Type COA code or name..."
      autoComplete="off"
      role="combobox"
      aria-expanded={open}
      aria-haspopup="listbox"
      onFocus={() => setOpen(true)}
      onChange={(event) => {
        setQuery(event.target.value);
        setOpen(true);
        if (!event.target.value.trim()) onChange(null);
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(false);
          setQuery(selectedLabel);
        }
      }}
    />
    {open && <>
      <button type="button" aria-label="Close COA options" className="fixed inset-0 z-[9998] cursor-default" onMouseDown={() => { setOpen(false); setQuery(selectedLabel); }} />
      <div role="listbox" className="absolute left-0 top-full z-[9999] mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-xl">
        {(waitingForSearch || lookup.isFetching) && <div className="px-3 py-3 text-sm text-slate-500">Searching COA...</div>}
        {!waitingForSearch && !lookup.isFetching && accounts.length ? accounts.map((account) => (
          <button
            key={account.id}
            type="button"
            role="option"
            aria-selected={account.id === value}
            className="block w-full border-b border-slate-100 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-emerald-50"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => choose(account)}
          >
            <div className="font-medium text-slate-800">{account.account_code} — {account.account_name}</div>
            {account.account_type && <div className="mt-0.5 text-xs text-slate-500">{account.account_type}</div>}
          </button>
        )) : null}
        {!waitingForSearch && !lookup.isFetching && !accounts.length && <div className="px-3 py-3 text-sm text-slate-500">No matching COA.</div>}
      </div>
    </>}
  </div>;
}

export default function SupplierInvoiceListPage() {
  const { hasPermission } = useAuthorization();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("invoices-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);
  useEffect(() => window.localStorage.setItem("invoices-page-size", String(pageSize)), [pageSize]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [filterSupplierId, setFilterSupplierId] = useState<number>();
  const [filterLocationId, setFilterLocationId] = useState<number>();
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const [submitError, setSubmitError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<any>(emptyForm());
  const recovery = useFormRecovery(`supplier-invoice:${editingId ? `edit:${editingId}` : "create"}`, form, open, validInvoiceInput);
  const [showAccounts, setShowAccounts] = useState(false);
  const [selectedInvoices, setSelectedInvoices] = useState<Record<number, boolean>>({});
  const sourceLocked = Boolean(form.goods_receipt_id || form.purchase_order_id);

  const fieldClass = (path: string) => fieldErrors[path] ? "border-red-500 ring-2 ring-red-200" : "";
  const fieldError = (path: string) => fieldErrors[path]
    ? <span role="alert" className="mt-1 block text-xs text-red-700">{fieldErrors[path]}</span>
    : null;

  useEffect(() => {
    const path = Object.keys(fieldErrors)[0];
    if (!path || !open) return;
    const matches = [...document.querySelectorAll<HTMLElement>("[data-field]")]
      .filter((element) => element.getAttribute("data-field") === path);
    const target = matches.find((element) => element.matches("input, select, textarea, button")) ?? matches[0];
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus?.();
  }, [fieldErrors, open]);

  const invoices = useQuery({ queryKey: ["supplier-invoices", page, pageSize, search, status, filterSupplierId, filterLocationId], queryFn: () => listInvoices({ page, page_size: pageSize, search: search || undefined, status: status || undefined, supplier_id: filterSupplierId ?? undefined, location_id: filterLocationId ?? undefined }) });
  const paymentOverview = useQuery({
    queryKey: ["supplier-invoice-payment-overview"],
    queryFn: async () => (await api.get("/ap-aging")).data as any,
  });
  const paymentSummary = useMemo(() => {
    const openRows: any[] = paymentOverview.data?.details ?? [];
    const paidRows: any[] = paymentOverview.data?.paid ?? [];
    const unpaidRows = openRows.filter((row) => Number(row.paid_amount || 0) <= 0);
    const partialRows = openRows.filter((row) => Number(row.paid_amount || 0) > 0 && Number(row.outstanding || 0) > 0);
    const fullyPaidRows = paidRows.filter((row) => String(row.payment_status || "").toUpperCase() === "PAID");

    const sumAmount = (rows: any[]) => rows.reduce((sum, row) => sum + Number(row.amount || 0), 0);
    const sumOutstanding = (rows: any[]) => rows.reduce((sum, row) => sum + Number(row.outstanding || 0), 0);

    return {
      totalCount: unpaidRows.length + partialRows.length + fullyPaidRows.length,
      totalValue: sumAmount(unpaidRows) + sumAmount(partialRows) + sumAmount(fullyPaidRows),
      unpaidCount: unpaidRows.length,
      unpaidValue: sumAmount(unpaidRows),
      partialCount: partialRows.length,
      partialValue: sumAmount(partialRows),
      partialOutstanding: sumOutstanding(partialRows),
      paidCount: fullyPaidRows.length,
      paidValue: sumAmount(fullyPaidRows),
      outstandingValue: Number(paymentOverview.data?.metrics?.total_outstanding || 0),
    };
  }, [paymentOverview.data]);
  const { data: suppliers = [] } = useSuppliers();
  const purchaseOrders = useQuery({ queryKey: ["invoice-pos"], queryFn: async () => (await purchaseOrderApi.list({ scope: "all", page_size: 100 })).data.items });
  const receipts = useQuery({ queryKey: ["invoice-receipts"], queryFn: listEligibleReceiptSources });
  const businessUnits = useQuery({ queryKey: ["business-units", "invoice", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const departments = useQuery({ queryKey: ["invoice-departments", form.business_unit_id], queryFn: () => listDepartments({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const locations = useQuery({ queryKey: ["invoice-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const filterLocations = useQuery({ queryKey: ["invoice-filter-locations", "active"], queryFn: () => listLocations({ is_active: true }) });

  useEffect(() => {
    if (open && !sourceLocked && !form.business_unit_id && businessUnits.data?.length === 1) setForm((current: any) => ({ ...current, business_unit_id: businessUnits.data![0].id }));
  }, [open, sourceLocked, form.business_unit_id, businessUnits.data]);

  const setLines = (lines: InvoiceLine[]) => setForm((current: any) => ({ ...current, lines }));
  const loadPo = async (id: number) => {
    if (!id) return setForm((current: any) => ({ ...current, purchase_order_id: null, goods_receipt_id: null, lines: [blankLine()] }));
    const po = (await purchaseOrderApi.detail(id)).data;
    setForm((current: any) => ({ ...current, vat_decision:"", purchase_order_id: id, goods_receipt_id: null, supplier_id: po.supplier_id, business_unit_id: po.business_unit_id, department_id: po.department_id, location_id: po.location_id, lines: po.items.map((item: any) => withTaxSnapshot(item, { purchase_order_item_id: item.id })) }));
  };
  const loadReceipt = async (id: number) => {
    if (!id) return setForm((current: any) => ({ ...current, goods_receipt_id: null, purchase_order_id: null, lines: [blankLine()] }));
    const receipt = (await goodsReceiptApi.detail(id)).data as any;
    setForm((current: any) => ({ ...current, vat_decision:"", goods_receipt_id: id, purchase_order_id: receipt.purchase_order_id ?? null, supplier_id: receipt.supplier_id, business_unit_id: receipt.business_unit_id, department_id: receipt.department_id, location_id: receipt.location_id, lines: receipt.items.map((item: any) => withTaxSnapshot(item, { purchase_order_item_id: item.purchase_order_item_id ?? null, goods_receipt_item_id: item.id })) }));
  };

  useEffect(() => {
    const receiptId = Number(searchParams.get("receipt_id"));
    if (!receiptId || !hasPermission("supplier_invoice.create")) return;
    setOpen(true);
    loadReceipt(receiptId).finally(() => setSearchParams({}, { replace: true }));
  // The query-string handoff is intentionally consumed only once on mount.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const editId = Number(searchParams.get("edit_id"));
    if (!editId || !hasPermission("supplier_invoice.edit")) return;
    const focusPath = searchParams.get("focus");
    const focusReason = searchParams.get("reason");
    setSubmitError(focusReason || "");
    setFieldErrors(focusPath ? { [focusPath]: focusReason || "Check this field." } : {});
    getInvoice(editId)
      .then((invoice) => {
        if (invoice.status !== "DRAFT") throw new Error("Only draft invoices can be edited");
        setEditingId(editId);
        const saved = recovery.load(`supplier-invoice:edit:${editId}`);
        setForm(saved ?? { ...emptyForm(), ...invoice,
          supplier_invoice_number: invoice.supplier_reference_pending ? "" :
            (invoice.supplier_invoice_number === invoice.internal_invoice_number ? "" : invoice.supplier_invoice_number),
          lines: invoice.lines.map((line) => ({ ...line })) });
        if (saved) recovery.notifyRestored();
        setOpen(true);
      })
      .catch((error) => {
        toast.error(error instanceof Error ? error.message : "Draft invoice could not be loaded");
        setOpen(false);
      })
      .finally(() => setSearchParams({}, { replace: true }));
  // The edit query-string handoff is intentionally consumed once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const calculation = useMemo(() => computeInvoiceTotals(form.lines, form), [form]);

  const changeVatDecision = (decision: string) => {
    const nextLines: InvoiceLine[] = decision === "NO_PPN_RECORDED"
      ? form.lines.map((line: InvoiceLine) => ({ ...line, is_taxable: false, tax_rate: 0, tax_amount: 0 }))
      : form.lines;
    const extra: Record<string, unknown> = { vat_decision: decision };
    if (decision === "NO_PPN_RECORDED") {
      extra.tax_invoice_number = "";
      extra.tax_invoice_date = "";
    }
    setForm(withSyncedDocumentTotal(form, nextLines, calculation.total, extra));
  };

  const changeLineTax = (index: number, patch: Partial<InvoiceLine>) => {
    const nextLines = form.lines.map((line: InvoiceLine, i: number) => i === index ? { ...line, ...patch } : line);
    setForm(withSyncedDocumentTotal(form, nextLines, calculation.total));
  };

  const receiptOptions = useMemo(() => {
    const rows = receipts.data ?? [];
    if (!editingId || !form.goods_receipt_id || rows.some((row: any) => row.id === Number(form.goods_receipt_id))) return rows;
    return [{
      id: Number(form.goods_receipt_id),
      receipt_number: form.receipt_number ?? `Receipt #${form.goods_receipt_id}`,
      supplier_name: form.supplier_name ?? "Current supplier",
      purchase_order_id: form.purchase_order_id,
      supplier_id: form.supplier_id,
      business_unit_id: form.business_unit_id,
      department_id: form.department_id,
      location_id: form.location_id,
    }, ...rows];
  }, [editingId, form.goods_receipt_id, form.receipt_number, form.supplier_name, form.purchase_order_id, form.supplier_id, form.business_unit_id, form.department_id, form.location_id, receipts.data]);
  const selectedSupplier: any = suppliers.find((supplier: any) => supplier.id === Number(form.supplier_id));
  const hasVat = calculation.tax > 0;

  const save = useMutation({
    mutationFn: (payload: any) => editingId ? updateInvoice(editingId, payload) : createInvoice(payload),
    onSuccess: (invoice) => {
      setSubmitError("");
      setFieldErrors({});
      toast.success(editingId ? "Draft invoice updated" : "Invoice saved as draft");
      recovery.clear();
      setOpen(false);
      setEditingId(null);
      setForm(emptyForm());

      // The detail page may already be open in a workspace tab. Replace the
      // stale pre-migration/detail response immediately, then refetch from the
      // source-aware API so resolved Location/Department/accounting state are current.
      queryClient.setQueryData(["supplier-invoice", String(invoice.id)], invoice);
      queryClient.setQueryData(["supplier-invoice", invoice.id], invoice);
      queryClient.invalidateQueries({ queryKey: ["supplier-invoice", String(invoice.id)], exact: true });
      queryClient.invalidateQueries({ queryKey: ["supplier-invoice", invoice.id], exact: true });
      queryClient.invalidateQueries({ queryKey: ["supplier-invoices"] });
      queryClient.invalidateQueries({ queryKey: ["invoice-receipts"] });
      queryClient.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      navigate(`/supplier-invoices/${invoice.id}`);
    },
    onError: (error) => {
      const info = parseInvoiceError(error);
      setSubmitError(info.message);
      setFieldErrors(Object.fromEntries(info.fields.map((issue) => [issue.path, issue.message])));
      toast.error(invoiceErrorMessage(error));
    },
  });
  const makeVoucher = useMutation({
    mutationFn: async () => {
      const ids = Object.entries(selectedInvoices).filter(([, v]) => v).map(([k]) => Number(k));
      if (!ids.length) throw new Error("Select at least one invoice");
      const rows = (invoices.data?.items ?? []).filter((row: any) => ids.includes(row.id));
      const locationIds = [...new Set(rows.map((r: any) => r.location_id).filter(Boolean))];
      if (!locationIds.length) throw new Error("Selected invoices have no location");
      if (locationIds.length > 1) throw new Error("All selected invoices must be from the same location");
      const nonPosted = rows.find((r: any) => r.status !== "POSTED");
      if (nonPosted) throw new Error(`Invoice ${nonPosted.internal_invoice_number} must be posted before creating a voucher`);
      const locationId = Number(locationIds[0]);
      const eligibleRows = (await listEligibleInvoices(locationId)).data as any[];
      const eligibleIds = new Set(eligibleRows.map((r: any) => r.id));
      const missing = ids.filter((id) => !eligibleIds.has(id));
      if (missing.length) throw new Error(`Invoice(s) ${missing.join(", ")} are not payable or already allocated to a voucher`);
      const allocations = eligibleRows
        .filter((r: any) => ids.includes(r.id))
        .map((r: any) => ({ supplier_invoice_id: r.id, allocated_amount: Number(r.available_balance) }));
      return (await createVoucher({ location_id: locationId, voucher_date: today(), allocations })).data;
    },
    onSuccess: (data: any) => {
      toast.success(`Voucher ${data.voucher_number} created`);
      setSelectedInvoices({});
      qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
      qc.invalidateQueries({ queryKey: ["payment-vouchers"] });
      navigate(`/finance/payment-vouchers/${data.id}`);
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || String(error)),
  });

  const failSubmit = (message: string, path?: string) => {
    setSubmitError(message);
    setFieldErrors(path ? { [path]: message } : {});
    toast.error(message);
  };

  const submit = () => {
    try {
      setSubmitError("");
      setFieldErrors({});
      if (!form.supplier_id) return failSubmit("Select a Supplier", "supplier_id");
      if (!form.business_unit_id) return failSubmit(sourceLocked ? "Source document has no Business Unit. Fix the source document before invoicing." : "Select a Business Unit", "business_unit_id");
      if (!form.department_id) return failSubmit(sourceLocked ? "Source document has no Department. Fix the source document before invoicing." : "Select a Department", "department_id");
      if (!form.location_id) return failSubmit(sourceLocked ? "Source document has no Location. Fix the source document before invoicing." : "Select a Location", "location_id");
      const invalidLineIndex = form.lines.findIndex((line: any) => !String(line.description ?? "").trim() || Number(line.quantity) <= 0 || Number(line.unit_price) < 0);
      if (!form.lines.length || invalidLineIndex >= 0) {
        const line = form.lines[invalidLineIndex];
        const path = !line ? "lines"
          : !String(line.description ?? "").trim() ? `lines[${invalidLineIndex}].description`
          : Number(line.quantity) <= 0 ? `lines[${invalidLineIndex}].quantity`
          : `lines[${invalidLineIndex}].unit_price`;
        return failSubmit("Complete all invoice lines with valid quantities and prices", path);
      }
      if (!form.vat_decision) return failSubmit("Confirm whether the supplier invoice records PPN.", "vat_decision");
      if (form.vat_decision==="DOCUMENT_PPN" && !hasVat) return failSubmit("Enter the PPN rate recorded on the invoice, or select No PPN recorded.", "vat_decision");
      if (form.vat_decision==="NO_PPN_RECORDED" && hasVat) return failSubmit("No PPN recorded requires zero invoice PPN.", "vat_decision");
      if (hasVat && !selectedSupplier?.is_pkp) return failSubmit("This invoice records PPN but the supplier is non-PKP. Check the invoice and supplier status; do not add PPN solely because the item is taxable.", "vat_decision");
      if (hasVat && form.source_type!=="HISTORICAL_IMPORT" && !form.tax_invoice_number.trim()) return failSubmit("Faktur Pajak Number is required for an invoice with PPN.", "tax_invoice_number");
      if (hasVat && form.source_type!=="HISTORICAL_IMPORT" && !form.tax_invoice_date) return failSubmit("Faktur Pajak Date is required for an invoice with PPN.", "tax_invoice_date");
      if (form.supplier_document_total != null && Math.abs(Number(form.supplier_document_total || 0) - calculation.total) >= 0.01) return failSubmit(`Document Total does not match the recalculated Invoice Total (${money(calculation.total)}). Update Document Total if you corrected PPN.`, "supplier_document_total");

      save.mutate(buildInvoicePayload(form, calculation));
    } catch (error) {
      failSubmit(invoiceErrorMessage(error));
    }
  };

  return <>
    <PageHeader title="Supplier Invoices" description="Catering receiving verifies complete supplier documents automatically. Use Supplier Invoices for exceptions and controlled corrections; AP payments remain separate." actions={<>
{hasPermission("supplier_invoice.create") ? <Button variant="outline" onClick={() => { const next = emptyForm(); if (businessUnits.data?.length === 1) next.business_unit_id = businessUnits.data[0].id; setEditingId(null); setSubmitError(""); setFieldErrors({}); const saved = recovery.load("supplier-invoice:create"); setForm(saved ?? next); if (saved) recovery.notifyRestored(); setOpen(true); }}>Manual Invoice</Button> : null}
{hasPermission("payment.manage") && <Button variant="outline" disabled={!Object.values(selectedInvoices).some(Boolean) || makeVoucher.isPending} loading={makeVoucher.isPending} onClick={() => makeVoucher.mutate()}>Payment Voucher</Button>}
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>} />
    <ModuleSummary
      metrics={[
        {
          label: "Invoices",
          value: paymentOverview.isLoading ? "…" : paymentSummary.totalCount,
          note: money(paymentSummary.totalValue),
        },
        {
          label: "Unpaid",
          value: paymentOverview.isLoading ? "…" : paymentSummary.unpaidCount,
          note: money(paymentSummary.unpaidValue),
        },
        {
          label: "Partially paid",
          value: paymentOverview.isLoading ? "…" : paymentSummary.partialCount,
          note: `${money(paymentSummary.partialValue)} value · ${money(paymentSummary.partialOutstanding)} remaining`,
        },
        {
          label: "Paid",
          value: paymentOverview.isLoading ? "…" : paymentSummary.paidCount,
          note: money(paymentSummary.paidValue),
        },
        {
          label: "Outstanding",
          value: money(paymentSummary.outstandingValue),
          note: "Unpaid balance",
        },
      ]}
    />
    <Card className="mt-3 overflow-hidden p-0">
      <div className="p-3 print:hidden">
        <ListToolbar
          search={search}
          searchPlaceholder="Search invoice, supplier reference, or number..."
          onSearch={(value) => { setSearch(value); setPage(1); }}
          filters={
            <select
              aria-label="Invoice status"
              className={`${input} w-auto min-w-[150px]`}
              value={status}
              onChange={(event) => { setStatus(event.target.value); setPage(1); }}
            >
              <option value="">All statuses</option>
              {["DRAFT", "VERIFIED", "REJECTED", "POSTED", "VOID"].map((value) => <option key={value}>{value}</option>)}
            </select>
          }
          advancedOpen={showFilters}
          onAdvancedToggle={() => setShowFilters((value) => !value)}
          advancedFilters={
            <div className="grid gap-2 md:grid-cols-2">
              <SearchableSelect label="Supplier" value={filterSupplierId} placeholder="Type supplier name..." options={suppliers.map((supplier: any) => ({ id: supplier.id, label: supplier.name, keywords: [supplier.name ?? "", supplier.code ?? ""] }))} onChange={(id) => { setFilterSupplierId(id); setPage(1); }} />
              <SearchableSelect label="Location" value={filterLocationId} disabled={filterLocations.isLoading} placeholder={filterLocations.isLoading ? "Loading locations..." : "Type location code or name..."} options={(filterLocations.data ?? []).map((item: any) => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code ?? "", item.name ?? ""] }))} onChange={(id) => { setFilterLocationId(id); setPage(1); }} />
            </div>
          }
          onRefresh={() => invoices.refetch()}
          footer={
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>{invoices.data?.total_items ?? 0} invoices match current filters</span>
              <label>Rows per page
                <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </label>
            </div>
          }
        />
      </div>
      <Table className="min-w-[900px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH className="w-12"><input type="checkbox" checked={(invoices.data?.items?.length ?? 0) > 0 && (invoices.data?.items ?? []).every((row: any) => !!selectedInvoices[row.id])} onChange={(event) => { const next: Record<number, boolean> = {}; (invoices.data?.items ?? []).forEach((row: any) => { if (row.status === "POSTED") next[row.id] = event.target.checked; }); setSelectedInvoices(next); }} /></TH><TH>Invoice</TH><TH>Supplier</TH><TH>Dates</TH><TH>Source Document</TH><TH numeric>PPN</TH><TH numeric>Total</TH><TH>Payment</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead><TBody>{invoices.data?.items.map((row: any) => <TR key={row.id} className="whitespace-nowrap"><TD className="w-12"><input type="checkbox" checked={!!selectedInvoices[row.id]} disabled={row.status !== "POSTED"} onChange={(event) => setSelectedInvoices((current) => ({ ...current, [row.id]: event.target.checked }))} /></TD><TD><TableCellStack primary={row.internal_invoice_number} secondary={row.supplier_invoice_number}/></TD><TD className="font-medium">{row.supplier_name}</TD><TD><TableCellStack primary={row.invoice_date} secondary={row.due_date ? `Due ${row.due_date}` : undefined}/></TD><TD>{row.receipt_number || "—"}</TD><TD numeric>{money(row.tax_amount)}</TD><TD numeric className="font-semibold">{money(row.total_amount)}</TD><TD>{(() => { const paymentStatus = String(row.payment_status || (Number(row.balance_amount ?? row.total_amount) <= 0 ? "PAID" : Number(row.paid_amount || 0) > 0 ? "PARTIALLY_PAID" : "UNPAID")).toUpperCase(); const paid = Number(row.paid_amount || 0); const outstanding = Number(row.balance_amount ?? row.total_amount ?? 0); return <TableCellStack primary={<Badge variant={paymentStatus === "PAID" ? "success" : paymentStatus === "PARTIALLY_PAID" ? "warning" : "danger"}>{paymentStatus === "PARTIALLY_PAID" ? "Partially Paid" : paymentStatus === "PAID" ? "Paid" : "Unpaid"}</Badge>} secondary={paymentStatus === "PAID" ? `Paid ${money(paid || row.total_amount)}` : paid > 0 ? `Paid ${money(paid)} · Due ${money(outstanding)}` : `Due ${money(outstanding)}`} />; })()}</TD><TD>{row.status}</TD><TD><div className="flex justify-end"><Button size="xs" variant="outline" onClick={() => navigate(`/supplier-invoices/${row.id}`)}>View</Button></div></TD></TR>)}
        {invoices.isPending && <TR><TD colSpan={10} className="p-10 text-center text-slate-500">Loading supplier invoices…</TD></TR>}
        {invoices.isError && <TR><TD colSpan={10} className="p-10 text-center text-red-700">Supplier invoices could not be loaded.</TD></TR>}
        {!invoices.isPending && !invoices.isError && !invoices.data?.items?.length && <TR><TD colSpan={10} className="p-10 text-center text-slate-500">No supplier invoices match these filters.</TD></TR>}
      </TBody></Table>
      <div className="px-3 pb-2">
        <Pagination
          page={page}
          pages={invoices.data?.total_pages ?? 1}
          total={invoices.data?.total_items ?? 0}
          pageSize={pageSize}
          noun="invoices"
          onChange={setPage}
        />
      </div>
    </Card>

    <Dialog open={open} onOpenChange={next => { if (!save.isPending) setOpen(next); }}><DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto"><DialogHeader><DialogTitle>{editingId ? "Edit Draft Supplier Invoice" : "Create Supplier Invoice"}</DialogTitle></DialogHeader><DialogBody className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">Posted Receipt<select className={input} value={form.goods_receipt_id ?? ""} onChange={(event) => loadReceipt(Number(event.target.value))}><option value="">Direct / no receipt</option>{receiptOptions.map((row: any) => <option key={row.id} value={row.id}>{row.receipt_number} — {row.supplier_name}</option>)}</select></label>
        <label className="text-sm">Purchase Order<select disabled={Boolean(form.goods_receipt_id)} className={input} value={form.purchase_order_id ?? ""} onChange={(event) => loadPo(Number(event.target.value))}><option value="">Direct / no PO</option>{purchaseOrders.data?.map((row: any) => <option key={row.id} value={row.id}>{row.po_number}</option>)}</select></label>
        <label className="text-sm">Supplier *<select data-field="supplier_id" disabled={sourceLocked} required className={`${input} ${fieldClass("supplier_id")}`} value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: Number(event.target.value) })}><option value={0}>Select supplier</option>{suppliers.map((supplier: any) => <option key={supplier.id} value={supplier.id}>{supplier.code} — {supplier.name}</option>)}</select><span className="mt-1 flex items-center gap-2 text-xs text-slate-500">Tax status: {selectedSupplier ? <Badge variant={selectedSupplier.is_pkp ? "success" : "secondary"}>{selectedSupplier.is_pkp ? "PKP" : "Non-PKP"}</Badge> : "—"}</span>{fieldError("supplier_id")}</label>
        <label className="text-sm">Business Unit *<select data-field="business_unit_id" disabled={sourceLocked} required className={`${input} ${fieldClass("business_unit_id")}`} value={form.business_unit_id ?? ""} onChange={(event) => setForm({ ...form, business_unit_id: Number(event.target.value), department_id: null, location_id: null })}><option value="">Select Business Unit</option>{businessUnits.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select>{fieldError("business_unit_id")}</label>
        <label className="text-sm">Department *<select data-field="department_id" disabled={sourceLocked || !form.business_unit_id} required className={`${input} ${fieldClass("department_id")}`} value={form.department_id ?? ""} onChange={(event) => setForm({ ...form, department_id: Number(event.target.value) })}><option value="">Select Department</option>{departments.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select>{fieldError("department_id")}</label>
        <label className="text-sm">Location *<select data-field="location_id" disabled={sourceLocked || !form.business_unit_id} required className={`${input} ${fieldClass("location_id")}`} value={form.location_id ?? ""} onChange={(event) => setForm({ ...form, location_id: Number(event.target.value) })}><option value="">Select Location</option>{locations.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select>{fieldError("location_id")}</label>
        <div className="space-y-1 text-sm"><span className="block">Invoice Number (System)</span><div className="flex h-10 items-center rounded-md border border-slate-200 bg-slate-50 px-3 font-medium text-emerald-800">{form.internal_invoice_number || "Generated automatically on Save Draft"}</div></div>
        <label className="text-sm">Supplier Reference (optional)<input data-field="supplier_invoice_number" className={`${input} ${fieldClass("supplier_invoice_number")}`} placeholder="Number printed on supplier's invoice, if available" value={form.supplier_invoice_number} onChange={(event) => setForm({ ...form, supplier_invoice_number: event.target.value })} />{fieldError("supplier_invoice_number")}</label>
        <div className="text-sm" data-field="supplier_document_total"><label>Document Total<CurrencyInput dataField="supplier_document_total" invalid={Boolean(fieldErrors.supplier_document_total)} value={Number(form.supplier_document_total||0)} onValueChange={value=>setForm({...form,supplier_document_total:value||null})}/></label>{fieldError("supplier_document_total")}{!fieldErrors.supplier_document_total && form.supplier_document_total != null && Math.abs(Number(form.supplier_document_total||0)-calculation.total) >= 0.01 ? <span className="mt-1 block text-xs text-amber-700">Differs from calculated Invoice Total ({money(calculation.total)}). Update if you corrected PPN.</span> : null}</div><label className="text-sm">Invoice Date *<input required type="date" className={input} value={form.invoice_date} onChange={(event) => setForm({ ...form, invoice_date: event.target.value, due_date: addDays(event.target.value, 30) })} /></label>
        <label className="text-sm">Due Date<input type="date" className={input} value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></label>
      </div>
      <div className="rounded border border-slate-200 p-3"><div className="flex flex-wrap items-center gap-3"><label className="text-xs font-medium">Does this supplier invoice record PPN?<select data-field="vat_decision" aria-label="Invoice PPN confirmation" required className={`ml-2 h-8 rounded border px-2 ${fieldClass("vat_decision")}`} value={form.vat_decision||""} onChange={event=>changeVatDecision(event.target.value)}><option value="">Choose from invoice</option><option value="NO_PPN_RECORDED">No PPN recorded</option><option value="DOCUMENT_PPN">PPN recorded</option></select></label><Badge variant={selectedSupplier?.is_pkp?"success":"secondary"}>{selectedSupplier?.is_pkp?"Supplier PKP":"Supplier non-PKP / unconfirmed"}</Badge>{fieldError("vat_decision")}</div></div>
      {sourceLocked && <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">Business Unit, Department and Location follow the source. Confirm PPN below from the supplier invoice.</div>}

      <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm text-slate-500">Accounting codes are applied automatically; open the account picker only when a line must be overridden.</span><Button variant="outline" size="sm" onClick={() => setShowAccounts((value) => !value)}>{showAccounts ? "Hide Account Codes" : "Assign Accounts"}</Button></div><div className="overflow-x-auto rounded border"><table className="min-w-[1250px] w-full text-sm"><thead><tr><th>Item / Description</th><th>Qty</th><th>UOM</th><th>Unit Price</th><th>Subtotal</th><th>PPN</th><th>Tax</th><th>Line Total</th>{showAccounts && <th>COA (auto if empty)</th>}<th/></tr></thead><tbody>{form.lines.map((line: any, index: number) => { const base=Number(line.quantity)*Number(line.unit_price); const lineTax=line.is_taxable?base*Number(line.tax_rate||0)/100:0; return <tr key={index} className="border-t"><td>{line.product_name ? <><div>{line.product_name}</div><div className="text-xs text-slate-500">{line.description}</div></> : <input required data-field={`lines[${index}].description`} className={`${input} ${fieldClass(`lines[${index}].description`)}`} value={line.description} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, description: event.target.value } : row))} />}{fieldError(`lines[${index}].description`)}</td><td><QuantityInput dataField={`lines[${index}].quantity`} invalid={Boolean(fieldErrors[`lines[${index}].quantity`])} value={Number(line.quantity)} onValueChange={(value) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, quantity: value } : row))} />{fieldError(`lines[${index}].quantity`)}</td><td><input className={input} value={line.uom ?? ""} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, uom: event.target.value } : row))} /></td><td><CurrencyInput dataField={`lines[${index}].unit_price`} invalid={Boolean(fieldErrors[`lines[${index}].unit_price`])} value={Number(line.unit_price)} onValueChange={(value) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, unit_price: value } : row))} />{fieldError(`lines[${index}].unit_price`)}</td><td className="text-right">{money(base)}</td><td><div className="flex items-center gap-1"><input data-field={`lines[${index}].is_taxable`} aria-label={`PPN applies to invoice line ${index+1}`} type="checkbox" disabled={form.vat_decision!=="DOCUMENT_PPN"} checked={Boolean(line.is_taxable)} onChange={event=>changeLineTax(index,{is_taxable:event.target.checked,tax_rate:event.target.checked?(form.lines[index]?.tax_rate||0):0})}/><input data-field={`lines[${index}].tax_rate`} aria-label={`Invoice PPN rate for line ${index+1}`} type="number" min="0" max="100" step="0.01" className={`h-8 w-20 rounded border px-2 text-right ${fieldClass(`lines[${index}].tax_rate`)}`} disabled={form.vat_decision!=="DOCUMENT_PPN"||!line.is_taxable} value={line.tax_rate||0} onChange={event=>changeLineTax(index,{tax_rate:Number(event.target.value)})}/><span>%</span></div>{fieldError(`lines[${index}].tax_rate`)}{fieldError(`lines[${index}].is_taxable`)}</td><td className="text-right">{money(lineTax)}</td><td className="text-right font-semibold">{money(base+lineTax)}</td>{showAccounts && <td><AccountPicker value={line.account_id} selectedCode={line.account_code} selectedName={line.account_name} onChange={(accountId) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, account_id: accountId } : row))} /></td>}<td>{!sourceLocked&&<Button variant="outline" size="xs" onClick={() => setLines(form.lines.filter((_: any, rowIndex: number) => rowIndex !== index))}>Remove</Button>}</td></tr> })}</tbody></table></div>
      {!sourceLocked && <Button variant="outline" onClick={() => setLines([...form.lines, blankLine()])}>Add Manual Line</Button>}

      {hasVat && <div className="rounded-lg border border-blue-200 bg-blue-50 p-4"><div className="mb-3 flex items-center justify-between"><div><div className="font-semibold text-blue-950">Faktur Pajak</div><div className="text-xs text-blue-700">Required because this invoice contains PPN.</div></div><Badge variant={selectedSupplier?.is_pkp ? "success" : "danger"}>{selectedSupplier?.is_pkp ? "Supplier PKP" : "Supplier is not PKP"}</Badge></div><div className="grid gap-3 md:grid-cols-2"><label className="text-sm">Faktur Pajak Number *<input data-field="tax_invoice_number" className={`${input} ${fieldClass("tax_invoice_number")}`} value={form.tax_invoice_number} onChange={(event)=>setForm({...form,tax_invoice_number:event.target.value})}/>{fieldError("tax_invoice_number")}</label><label className="text-sm">Faktur Pajak Date *<input data-field="tax_invoice_date" type="date" className={`${input} ${fieldClass("tax_invoice_date")}`} value={form.tax_invoice_date} onChange={(event)=>setForm({...form,tax_invoice_date:event.target.value})}/>{fieldError("tax_invoice_date")}</label></div></div>}

      <div className="grid gap-3 md:grid-cols-2"><label className="text-sm">Discount<CurrencyInput dataField="discount_amount" invalid={Boolean(fieldErrors.discount_amount)} value={Number(form.discount_amount)} onValueChange={(value) => setForm(withSyncedDocumentTotal(form, form.lines, calculation.total, { discount_amount: value }))} />{fieldError("discount_amount")}</label><label className="text-sm">Withholding Tax<CurrencyInput dataField="withholding_tax_amount" invalid={Boolean(fieldErrors.withholding_tax_amount)} value={Number(form.withholding_tax_amount)} onValueChange={(value) => setForm(withSyncedDocumentTotal(form, form.lines, calculation.total, { withholding_tax_amount: value }))} />{fieldError("withholding_tax_amount")}</label></div>
      <div className="rounded border border-slate-200 p-3 space-y-3">
         <h3 className="font-semibold text-sm">Supplier charges (correct only when required)</h3>
         <div className="grid gap-3 md:grid-cols-3">
           {(["shipping","admin","other"] as const).map(kind=><div className="space-y-1" key={kind} data-field={`${kind}_fee_account_id`}>
             <label className="text-sm capitalize">{kind} Fee<CurrencyInput dataField={`${kind}_fee_amount`} invalid={Boolean(fieldErrors[`${kind}_fee_amount`])} value={Number(form[`${kind}_fee_amount`]||0)} onValueChange={value=>setForm((current:any)=>withSyncedDocumentTotal(current,current.lines,computeInvoiceTotals(current.lines,current).total,{ [`${kind}_fee_amount`]: value }))}/>{fieldError(`${kind}_fee_amount`)}</label>
             <div className="text-xs text-slate-600">Expense account</div>
             <AccountPicker value={form[`${kind}_fee_account_id`]} onChange={id=>setForm((current:any)=>({...current,[`${kind}_fee_account_id`]:id}))}/>{fieldError(`${kind}_fee_account_id`)}
           </div>)}
         </div>
         {Number(form.other_fee_amount)>0&&<label className="text-sm">Other fee description<input data-field="other_fee_description" className={`${input} ${fieldClass("other_fee_description")}`} value={form.other_fee_description||""} onChange={e=>setForm({...form,other_fee_description:e.target.value})}/>{fieldError("other_fee_description")}</label>}
         <label className="text-sm">Supplier document link<input type="url" className={input} value={form.supplier_document_url||""} onChange={e=>setForm({...form,supplier_document_url:e.target.value})}/></label>
       </div>
       <div className="ml-auto max-w-sm space-y-2 rounded-lg border bg-slate-50 p-4 text-sm"><div className="flex justify-between"><span>Subtotal</span><span>{money(calculation.subtotal)}</span></div><div className="flex justify-between"><span>PPN</span><span>{money(calculation.tax)}</span></div>{Number(form.discount_amount)>0&&<div className="flex justify-between"><span>Discount</span><span>({money(form.discount_amount)})</span></div>}{Number(form.withholding_tax_amount)>0&&<div className="flex justify-between"><span>Withholding</span><span>({money(form.withholding_tax_amount)})</span></div>}<div className="flex justify-between border-t pt-2 text-lg font-bold"><span>Invoice Total</span><span>{money(calculation.total)}</span></div></div>
      <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-2" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      {submitError && <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{submitError}</div>}
    </DialogBody><DialogFooter><FormRecoveryActions failed={recovery.failed} disabled={save.isPending} onDiscard={() => { recovery.clear(); setOpen(false); setEditingId(null); setForm(emptyForm()); }} /><Button variant="outline" disabled={save.isPending} onClick={() => setOpen(false)}>Close</Button><Button type="button" loading={save.isPending} onClick={submit}>{editingId ? "Save Changes" : "Save Draft"}</Button></DialogFooter></DialogContent></Dialog>
  </>;
}

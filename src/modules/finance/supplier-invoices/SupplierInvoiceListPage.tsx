import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import QuantityInput from "@/components/form/QuantityInput";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { getAccounts } from "@/modules/master/chart-of-accounts/api";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import purchaseOrderApi from "@/modules/purchasing/purchase-order/api/purchaseOrderApi";
import goodsReceiptApi from "@/modules/purchasing/goods-receipts/api/goodsReceiptApi";
import { createInvoice, getInvoice, InvoiceLine, listEligibleReceiptSources, listInvoices, updateInvoice } from "./api";
import useAuthorization from "@/hooks/useAuthorization";

const today = () => new Date().toISOString().slice(0, 10);
const addDays = (value: string, days: number) => {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
};
const blankLine = (): InvoiceLine => ({ description: "", quantity: 0, uom: "", unit_price: 0, account_id: null, is_taxable: false, tax_rate: 0, tax_amount: 0 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const emptyForm = (): any => ({ supplier_id: 0, supplier_invoice_number: "", invoice_date: today(), received_date: today(), due_date: addDays(today(), 30), purchase_order_id: null, goods_receipt_id: null, business_unit_id: null, department_id: null, location_id: null, currency: "IDR", discount_amount: 0, withholding_tax_amount: 0, tax_invoice_number: "", tax_invoice_date: "", notes: "", source_type: "LIVE", lines: [blankLine()] });
const invoiceErrorMessage = (error: unknown) => {
  if (!axios.isAxiosError(error)) return "Invoice could not be saved";
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: any) => item?.msg ?? String(item)).join("; ");
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as any).message);
  return error.message || "Invoice could not be saved";
};

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
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<any>(emptyForm());
  const sourceLocked = Boolean(form.goods_receipt_id || form.purchase_order_id);

  const invoices = useQuery({ queryKey: ["supplier-invoices", page, search, status], queryFn: () => listInvoices({ page, page_size: 20, search: search || undefined, status: status || undefined }) });
  const { data: suppliers = [] } = useSuppliers();
  const purchaseOrders = useQuery({ queryKey: ["invoice-pos"], queryFn: async () => (await purchaseOrderApi.list({ scope: "all", page_size: 100 })).data.items });
  const receipts = useQuery({ queryKey: ["invoice-receipts"], queryFn: listEligibleReceiptSources });
  const businessUnits = useQuery({ queryKey: ["business-units", "invoice", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const departments = useQuery({ queryKey: ["invoice-departments", form.business_unit_id], queryFn: () => listDepartments({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const locations = useQuery({ queryKey: ["invoice-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });

  useEffect(() => {
    if (open && !sourceLocked && !form.business_unit_id && businessUnits.data?.length === 1) setForm((current: any) => ({ ...current, business_unit_id: businessUnits.data![0].id }));
  }, [open, sourceLocked, form.business_unit_id, businessUnits.data]);

  const setLines = (lines: InvoiceLine[]) => setForm((current: any) => ({ ...current, lines }));
  const loadPo = async (id: number) => {
    if (!id) return setForm((current: any) => ({ ...current, purchase_order_id: null, goods_receipt_id: null, lines: [blankLine()] }));
    const po = (await purchaseOrderApi.detail(id)).data;
    setForm((current: any) => ({ ...current, purchase_order_id: id, goods_receipt_id: null, supplier_id: po.supplier_id, business_unit_id: po.business_unit_id, department_id: po.department_id, location_id: po.location_id, lines: po.items.map((item: any) => withTaxSnapshot(item, { purchase_order_item_id: item.id })) }));
  };
  const loadReceipt = async (id: number) => {
    if (!id) return setForm((current: any) => ({ ...current, goods_receipt_id: null, purchase_order_id: null, lines: [blankLine()] }));
    const receipt = (await goodsReceiptApi.detail(id)).data as any;
    setForm((current: any) => ({ ...current, goods_receipt_id: id, purchase_order_id: receipt.purchase_order_id ?? null, supplier_id: receipt.supplier_id, business_unit_id: receipt.business_unit_id, department_id: receipt.department_id, location_id: receipt.location_id, lines: receipt.items.map((item: any) => withTaxSnapshot(item, { purchase_order_item_id: item.purchase_order_item_id ?? null, goods_receipt_item_id: item.id })) }));
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
    setSubmitError("");
    setOpen(true);
    getInvoice(editId)
      .then((invoice) => {
        if (invoice.status !== "DRAFT") throw new Error("Only draft invoices can be edited");
        setEditingId(editId);
        setForm({ ...emptyForm(), ...invoice, lines: invoice.lines.map((line) => ({ ...line })) });
      })
      .catch((error) => {
        toast.error(error instanceof Error ? error.message : "Draft invoice could not be loaded");
        setOpen(false);
      })
      .finally(() => setSearchParams({}, { replace: true }));
  // The edit query-string handoff is intentionally consumed once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const calculation = useMemo(() => {
    const subtotal = form.lines.reduce((sum: number, line: any) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0), 0);
    const tax = form.lines.reduce((sum: number, line: any) => {
      const base = Number(line.quantity || 0) * Number(line.unit_price || 0);
      return sum + (line.is_taxable ? base * Number(line.tax_rate || 0) / 100 : 0);
    }, 0);
    const total = subtotal - Number(form.discount_amount || 0) + tax - Number(form.withholding_tax_amount || 0);
    return { subtotal, tax, total };
  }, [form.lines, form.discount_amount, form.withholding_tax_amount]);

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
      toast.success(editingId ? "Draft invoice updated" : "Invoice saved as draft");
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
      const message = invoiceErrorMessage(error);
      setSubmitError(message);
      toast.error(message);
    },
  });

  const failSubmit = (message: string) => {
    setSubmitError(message);
    toast.error(message);
  };

  const submit = () => {
    try {
      setSubmitError("");
      if (!form.supplier_id) return failSubmit("Select a Supplier");
      if (!form.supplier_invoice_number.trim()) return failSubmit("Supplier Invoice Number is required");
      if (!form.business_unit_id) return failSubmit(sourceLocked ? "Source document has no Business Unit. Fix the source document before invoicing." : "Select a Business Unit");
      if (!form.department_id) return failSubmit(sourceLocked ? "Source document has no Department. Fix the source document before invoicing." : "Select a Department");
      if (!form.location_id) return failSubmit(sourceLocked ? "Source document has no Location. Fix the source document before invoicing." : "Select a Location");
      if (!form.lines.length || form.lines.some((line: any) => !String(line.description ?? "").trim() || Number(line.quantity) <= 0 || Number(line.unit_price) < 0)) return failSubmit("Complete all invoice lines with valid quantities and prices");
      if (hasVat && !selectedSupplier?.is_pkp) return failSubmit("This invoice contains PPN. Mark the supplier as PKP in Supplier Master first.");
      if (hasVat && !form.tax_invoice_number.trim()) return failSubmit("Faktur Pajak Number is required for an invoice with PPN.");
      if (hasVat && !form.tax_invoice_date) return failSubmit("Faktur Pajak Date is required for an invoice with PPN.");

      const payload = {
        ...form,
        tax_amount: calculation.tax,
        tax_invoice_number: form.tax_invoice_number || null,
        tax_invoice_date: form.tax_invoice_date || null,
        due_date: form.due_date || null,
        lines: form.lines.map((line: any) => ({
          ...line,
          line_amount: undefined,
          tax_amount: undefined,
          line_total: undefined,
        })),
      };
      save.mutate(payload);
    } catch (error) {
      failSubmit(invoiceErrorMessage(error));
    }
  };

  return <>
    <PageHeader title="Supplier Invoices" description="Create invoices from posted receiving documents or enter a direct supplier invoice." actions={hasPermission("supplier_invoice.create") ? <Button onClick={() => { const next = emptyForm(); if (businessUnits.data?.length === 1) next.business_unit_id = businessUnits.data[0].id; setEditingId(null); setForm(next); setOpen(true); }}>Create Invoice</Button> : null} />
    <Card className="mt-6"><div className="mb-4 flex gap-3"><input className={input} placeholder="Search invoices" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /><select className={input} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{["DRAFT", "VERIFIED", "REJECTED", "POSTED", "VOID"].map((value) => <option key={value}>{value}</option>)}</select></div><Table className="min-w-[900px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Invoice</TH><TH>Supplier</TH><TH>Dates</TH><TH>Source Document</TH><TH numeric>PPN</TH><TH numeric>Total</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead><TBody>{invoices.data?.items.map((row: any) => <TR key={row.id} className="whitespace-nowrap"><TD><TableCellStack primary={row.internal_invoice_number} secondary={row.supplier_invoice_number}/></TD><TD className="font-medium">{row.supplier_name}</TD><TD><TableCellStack primary={row.invoice_date} secondary={row.due_date ? `Due ${row.due_date}` : undefined}/></TD><TD>{row.receipt_number || "—"}</TD><TD numeric>{money(row.tax_amount)}</TD><TD numeric className="font-semibold">{money(row.total_amount)}</TD><TD>{row.status}</TD><TD><div className="flex justify-end"><Button size="xs" variant="outline" onClick={() => navigate(`/supplier-invoices/${row.id}`)}>View</Button></div></TD></TR>)}</TBody></Table><div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!invoices.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!invoices.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></Card>

    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setEditingId(null); }}><DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto"><DialogHeader><DialogTitle>{editingId ? "Edit Draft Supplier Invoice" : "Create Supplier Invoice"}</DialogTitle></DialogHeader><DialogBody className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">Posted Receipt<select className={input} value={form.goods_receipt_id ?? ""} onChange={(event) => loadReceipt(Number(event.target.value))}><option value="">Direct / no receipt</option>{receiptOptions.map((row: any) => <option key={row.id} value={row.id}>{row.receipt_number} — {row.supplier_name}</option>)}</select></label>
        <label className="text-sm">Purchase Order<select disabled={Boolean(form.goods_receipt_id)} className={input} value={form.purchase_order_id ?? ""} onChange={(event) => loadPo(Number(event.target.value))}><option value="">Direct / no PO</option>{purchaseOrders.data?.map((row: any) => <option key={row.id} value={row.id}>{row.po_number}</option>)}</select></label>
        <label className="text-sm">Supplier *<select disabled={sourceLocked} required className={input} value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: Number(event.target.value) })}><option value={0}>Select supplier</option>{suppliers.map((supplier: any) => <option key={supplier.id} value={supplier.id}>{supplier.code} — {supplier.name}</option>)}</select><span className="mt-1 flex items-center gap-2 text-xs text-slate-500">Tax status: {selectedSupplier ? <Badge variant={selectedSupplier.is_pkp ? "success" : "secondary"}>{selectedSupplier.is_pkp ? "PKP" : "Non-PKP"}</Badge> : "—"}</span></label>
        <label className="text-sm">Business Unit *<select disabled={sourceLocked} required className={input} value={form.business_unit_id ?? ""} onChange={(event) => setForm({ ...form, business_unit_id: Number(event.target.value), department_id: null, location_id: null })}><option value="">Select Business Unit</option>{businessUnits.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Department *<select disabled={sourceLocked || !form.business_unit_id} required className={input} value={form.department_id ?? ""} onChange={(event) => setForm({ ...form, department_id: Number(event.target.value) })}><option value="">Select Department</option>{departments.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Location *<select disabled={sourceLocked || !form.business_unit_id} required className={input} value={form.location_id ?? ""} onChange={(event) => setForm({ ...form, location_id: Number(event.target.value) })}><option value="">Select Location</option>{locations.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Supplier Invoice Number *<input required className={input} value={form.supplier_invoice_number} onChange={(event) => setForm({ ...form, supplier_invoice_number: event.target.value })} /></label>
        <label className="text-sm">Invoice Date *<input required type="date" className={input} value={form.invoice_date} onChange={(event) => setForm({ ...form, invoice_date: event.target.value, due_date: addDays(event.target.value, 30) })} /></label>
        <label className="text-sm">Due Date<input type="date" className={input} value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></label>
      </div>
      {sourceLocked && <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">Business Unit, Department, Location, and item PPN treatment are inherited from the selected PO/Receiving document.</div>}

      <div className="overflow-x-auto rounded border"><table className="min-w-[1250px] w-full text-sm"><thead><tr><th>Item / Description</th><th>Qty</th><th>UOM</th><th>Unit Price</th><th>Subtotal</th><th>PPN</th><th>Tax</th><th>Line Total</th><th>COA</th><th/></tr></thead><tbody>{form.lines.map((line: any, index: number) => { const base=Number(line.quantity)*Number(line.unit_price); const lineTax=line.is_taxable?base*Number(line.tax_rate||0)/100:0; return <tr key={index} className="border-t"><td>{line.product_name ? <><div>{line.product_name}</div><div className="text-xs text-slate-500">{line.description}</div></> : <input required className={input} value={line.description} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, description: event.target.value } : row))} />}</td><td><QuantityInput value={Number(line.quantity)} onValueChange={(value) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, quantity: value } : row))} /></td><td><input className={input} value={line.uom ?? ""} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, uom: event.target.value } : row))} /></td><td><CurrencyInput value={Number(line.unit_price)} onValueChange={(value) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, unit_price: value } : row))} /></td><td className="text-right">{money(base)}</td><td>{line.is_taxable ? <Badge variant="info">{Number(line.tax_rate||0)}%</Badge> : <Badge variant="secondary">Non PPN</Badge>}</td><td className="text-right">{money(lineTax)}</td><td className="text-right font-semibold">{money(base+lineTax)}</td><td><AccountPicker value={line.account_id} selectedCode={line.account_code} selectedName={line.account_name} onChange={(accountId) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, account_id: accountId } : row))} /></td><td>{!sourceLocked&&<Button variant="outline" size="xs" onClick={() => setLines(form.lines.filter((_: any, rowIndex: number) => rowIndex !== index))}>Remove</Button>}</td></tr> })}</tbody></table></div>
      {!sourceLocked && <Button variant="outline" onClick={() => setLines([...form.lines, blankLine()])}>Add Manual Line</Button>}

      {hasVat && <div className="rounded-lg border border-blue-200 bg-blue-50 p-4"><div className="mb-3 flex items-center justify-between"><div><div className="font-semibold text-blue-950">Faktur Pajak</div><div className="text-xs text-blue-700">Required because this invoice contains PPN.</div></div><Badge variant={selectedSupplier?.is_pkp ? "success" : "danger"}>{selectedSupplier?.is_pkp ? "Supplier PKP" : "Supplier is not PKP"}</Badge></div><div className="grid gap-3 md:grid-cols-2"><label className="text-sm">Faktur Pajak Number *<input className={input} value={form.tax_invoice_number} onChange={(event)=>setForm({...form,tax_invoice_number:event.target.value})}/></label><label className="text-sm">Faktur Pajak Date *<input type="date" className={input} value={form.tax_invoice_date} onChange={(event)=>setForm({...form,tax_invoice_date:event.target.value})}/></label></div></div>}

      <div className="grid gap-3 md:grid-cols-2"><label className="text-sm">Discount<CurrencyInput value={Number(form.discount_amount)} onValueChange={(value) => setForm({ ...form, discount_amount: value })} /></label><label className="text-sm">Withholding Tax<CurrencyInput value={Number(form.withholding_tax_amount)} onValueChange={(value) => setForm({ ...form, withholding_tax_amount: value })} /></label></div>
      <div className="ml-auto max-w-sm space-y-2 rounded-lg border bg-slate-50 p-4 text-sm"><div className="flex justify-between"><span>Subtotal</span><span>{money(calculation.subtotal)}</span></div><div className="flex justify-between"><span>PPN</span><span>{money(calculation.tax)}</span></div>{Number(form.discount_amount)>0&&<div className="flex justify-between"><span>Discount</span><span>({money(form.discount_amount)})</span></div>}{Number(form.withholding_tax_amount)>0&&<div className="flex justify-between"><span>Withholding</span><span>({money(form.withholding_tax_amount)})</span></div>}<div className="flex justify-between border-t pt-2 text-lg font-bold"><span>Invoice Total</span><span>{money(calculation.total)}</span></div></div>
      <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-2" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      {submitError && <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{submitError}</div>}
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => { setOpen(false); setEditingId(null); }}>Cancel</Button><Button type="button" loading={save.isPending} onClick={submit}>{editingId ? "Save Changes" : "Save Draft"}</Button></DialogFooter></DialogContent></Dialog>
  </>;
}

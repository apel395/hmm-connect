import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import QuantityInput from "@/components/form/QuantityInput";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import purchaseOrderApi from "@/modules/purchasing/purchase-order/api/purchaseOrderApi";
import goodsReceiptApi from "@/modules/purchasing/goods-receipts/api/goodsReceiptApi";
import { createInvoice, InvoiceLine, listEligibleReceiptSources, listInvoices } from "./api";

const today = () => new Date().toISOString().slice(0, 10);
const blankLine = (): InvoiceLine => ({ description: "", quantity: 0, uom: "", unit_price: 0, account_id: null });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const emptyForm = (): any => ({ supplier_id: 0, supplier_invoice_number: "", invoice_date: today(), received_date: today(), due_date: "", purchase_order_id: null, goods_receipt_id: null, business_unit_id: null, department_id: null, location_id: null, currency: "IDR", discount_amount: 0, tax_amount: 0, withholding_tax_amount: 0, notes: "", source_type: "LIVE", lines: [blankLine()] });

export default function SupplierInvoiceListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>(emptyForm());
  const sourceLocked = Boolean(form.goods_receipt_id || form.purchase_order_id);

  const invoices = useQuery({ queryKey: ["supplier-invoices", page, search, status], queryFn: () => listInvoices({ page, page_size: 20, search: search || undefined, status: status || undefined }) });
  const { data: suppliers = [] } = useSuppliers();
  const accounts = useQuery({ queryKey: ["coa-invoice-lookup"], queryFn: () => getAccountLookup({ is_active: true, is_posting: true }) });
  const purchaseOrders = useQuery({ queryKey: ["invoice-pos"], queryFn: async () => (await purchaseOrderApi.list({ scope: "all", page_size: 100 })).data.items });
  const receipts = useQuery({ queryKey: ["invoice-receipts"], queryFn: listEligibleReceiptSources });
  const businessUnits = useQuery({ queryKey: ["business-units", "invoice", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const departments = useQuery({ queryKey: ["invoice-departments", form.business_unit_id], queryFn: () => listDepartments({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const locations = useQuery({ queryKey: ["invoice-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });

  useEffect(() => {
    if (open && !sourceLocked && !form.business_unit_id && businessUnits.data?.length === 1) {
      setForm((current: any) => ({ ...current, business_unit_id: businessUnits.data![0].id }));
    }
  }, [open, sourceLocked, form.business_unit_id, businessUnits.data]);

  const setLines = (lines: InvoiceLine[]) => setForm((current: any) => ({ ...current, lines }));
  const loadPo = async (id: number) => {
    if (!id) return setForm((current: any) => ({ ...current, purchase_order_id: null, goods_receipt_id: null }));
    const po = (await purchaseOrderApi.detail(id)).data;
    setForm((current: any) => ({ ...current, purchase_order_id: id, goods_receipt_id: null, supplier_id: po.supplier_id, business_unit_id: po.business_unit_id, department_id: po.department_id, location_id: po.location_id, lines: po.items.map((item: any) => ({ product_id: item.product_id, product_code: item.product_code, product_name: item.product_name, purchase_order_item_id: item.id, description: item.description || item.product_name, quantity: Number(item.quantity), uom: item.uom, unit_price: Number(item.unit_price), account_id: null })) }));
  };
  const loadReceipt = async (id: number) => {
    if (!id) return setForm((current: any) => ({ ...current, goods_receipt_id: null, purchase_order_id: null }));
    const receipt = (await goodsReceiptApi.detail(id)).data as any;
    setForm((current: any) => ({ ...current, goods_receipt_id: id, purchase_order_id: receipt.purchase_order_id ?? null, supplier_id: receipt.supplier_id, business_unit_id: receipt.business_unit_id, department_id: receipt.department_id, location_id: receipt.location_id, lines: receipt.items.map((item: any) => ({ product_id: item.product_id, product_code: item.product_code, product_name: item.product_name, purchase_order_item_id: item.purchase_order_item_id ?? null, goods_receipt_item_id: item.id, description: item.product_name, quantity: Number(item.quantity), uom: item.uom, unit_price: Number(item.unit_cost), account_id: null })) }));
  };

  useEffect(() => {
    const receiptId = Number(searchParams.get("receipt_id"));
    if (!receiptId) return;
    setOpen(true);
    loadReceipt(receiptId).finally(() => setSearchParams({}, { replace: true }));
  }, []);

  const total = useMemo(() => form.lines.reduce((sum: number, line: any) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0), 0) - Number(form.discount_amount || 0) + Number(form.tax_amount || 0) - Number(form.withholding_tax_amount || 0), [form]);

  const save = useMutation({
    mutationFn: () => createInvoice({ ...form, due_date: form.due_date || null, lines: form.lines.map((line: any) => ({ ...line, line_amount: undefined })) }),
    onSuccess: (invoice) => {
      toast.success("Invoice saved as draft");
      setOpen(false);
      setForm(emptyForm());
      queryClient.invalidateQueries({ queryKey: ["supplier-invoices"] });
      queryClient.invalidateQueries({ queryKey: ["invoice-receipts"] });
      queryClient.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      navigate(`/supplier-invoices/${invoice.id}`);
    },
    onError: (error) => toast.error(axios.isAxiosError(error) && typeof error.response?.data?.detail === "string" ? error.response.data.detail : "Invoice could not be saved"),
  });

  const submit = () => {
    if (!form.supplier_id) return toast.error("Select a Supplier");
    if (!form.supplier_invoice_number.trim()) return toast.error("Supplier Invoice Number is required");
    if (!form.business_unit_id) return toast.error(sourceLocked ? "Source document has no Business Unit. Fix the source document before invoicing." : "Select a Business Unit");
    if (!form.department_id) return toast.error(sourceLocked ? "Source document has no Department. Fix the source document before invoicing." : "Select a Department");
    if (!form.location_id) return toast.error(sourceLocked ? "Source document has no Location. Fix the source document before invoicing." : "Select a Location");
    if (!form.lines.length || form.lines.some((line: any) => !line.description?.trim() || Number(line.quantity) <= 0 || Number(line.unit_price) < 0)) return toast.error("Complete all invoice lines with valid quantities and prices");
    save.mutate();
  };

  return <>
    <PageHeader title="Supplier Invoices" description="Create invoices from posted receiving documents or enter a direct supplier invoice." actions={<Button onClick={() => { const next = emptyForm(); if (businessUnits.data?.length === 1) next.business_unit_id = businessUnits.data[0].id; setForm(next); setOpen(true); }}>Create Invoice</Button>} />
    <Card className="mt-6"><div className="mb-4 flex gap-3"><input className={input} placeholder="Search invoices" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /><select className={input} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{["DRAFT", "VERIFIED", "REJECTED", "POSTED", "VOID"].map((value) => <option key={value}>{value}</option>)}</select></div><div className="overflow-x-auto"><table className="min-w-[1100px] w-full text-sm"><thead><tr><th>Internal Invoice</th><th>Supplier Invoice</th><th>Supplier</th><th>Invoice Date</th><th>Due Date</th><th>Receipt</th><th>Total</th><th>Status</th><th>Action</th></tr></thead><tbody>{invoices.data?.items.map((row: any) => <tr key={row.id} className="border-t"><td>{row.internal_invoice_number}</td><td>{row.supplier_invoice_number}</td><td>{row.supplier_name}</td><td>{row.invoice_date}</td><td>{row.due_date || "—"}</td><td>{row.receipt_number || "—"}</td><td>{money(row.total_amount)}</td><td>{row.status}</td><td><Button size="xs" variant="outline" onClick={() => navigate(`/supplier-invoices/${row.id}`)}>View</Button></td></tr>)}</tbody></table></div><div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!invoices.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!invoices.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></Card>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>Create Supplier Invoice</DialogTitle></DialogHeader><DialogBody className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">Posted Receipt<select className={input} value={form.goods_receipt_id ?? ""} onChange={(event) => loadReceipt(Number(event.target.value))}><option value="">Direct / no receipt</option>{receipts.data?.map((row: any) => <option key={row.id} value={row.id}>{row.receipt_number} — {row.supplier_name}</option>)}</select></label>
        <label className="text-sm">Purchase Order<select disabled={Boolean(form.goods_receipt_id)} className={input} value={form.purchase_order_id ?? ""} onChange={(event) => loadPo(Number(event.target.value))}><option value="">Direct / no PO</option>{purchaseOrders.data?.map((row: any) => <option key={row.id} value={row.id}>{row.po_number}</option>)}</select></label>
        <label className="text-sm">Supplier *<select disabled={sourceLocked} required className={input} value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: Number(event.target.value) })}><option value={0}>Select supplier</option>{suppliers.map((supplier: any) => <option key={supplier.id} value={supplier.id}>{supplier.code} — {supplier.name}</option>)}</select></label>
        <label className="text-sm">Business Unit *<select disabled={sourceLocked} required className={input} value={form.business_unit_id ?? ""} onChange={(event) => setForm({ ...form, business_unit_id: Number(event.target.value), department_id: null, location_id: null })}><option value="">Select Business Unit</option>{businessUnits.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Department *<select disabled={sourceLocked || !form.business_unit_id} required className={input} value={form.department_id ?? ""} onChange={(event) => setForm({ ...form, department_id: Number(event.target.value) })}><option value="">Select Department</option>{departments.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Location *<select disabled={sourceLocked || !form.business_unit_id} required className={input} value={form.location_id ?? ""} onChange={(event) => setForm({ ...form, location_id: Number(event.target.value) })}><option value="">Select Location</option>{locations.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Supplier Invoice Number *<input required className={input} value={form.supplier_invoice_number} onChange={(event) => setForm({ ...form, supplier_invoice_number: event.target.value })} /></label>
        <label className="text-sm">Invoice Date *<input required type="date" className={input} value={form.invoice_date} onChange={(event) => setForm({ ...form, invoice_date: event.target.value })} /></label>
        <label className="text-sm">Due Date<input type="date" className={input} value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></label>
      </div>
      {sourceLocked && <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">Business Unit, Department, and Location are inherited from the selected PO/Receiving document and cannot be changed here.</div>}
      <div className="overflow-x-auto rounded border"><table className="min-w-[1000px] w-full text-sm"><thead><tr><th>Item / Description</th><th>Qty</th><th>UOM</th><th>Unit Price</th><th>Line Total</th><th>COA</th><th/></tr></thead><tbody>{form.lines.map((line: any, index: number) => <tr key={index} className="border-t"><td>{line.product_name ? <><div>{line.product_name}</div><div className="text-xs text-slate-500">{line.description}</div></> : <input required className={input} value={line.description} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, description: event.target.value } : row))} />}</td><td><QuantityInput value={Number(line.quantity)} onValueChange={(value) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, quantity: value } : row))} /></td><td><input className={input} value={line.uom ?? ""} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, uom: event.target.value } : row))} /></td><td><CurrencyInput value={Number(line.unit_price)} onValueChange={(value) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, unit_price: value } : row))} /></td><td className="text-right">{money(Number(line.quantity) * Number(line.unit_price))}</td><td><select className={input} value={line.account_id ?? ""} onChange={(event) => setLines(form.lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, account_id: Number(event.target.value) || null } : row))}><option value="">Use posting rule</option>{accounts.data?.map((account: any) => <option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select></td><td><Button variant="outline" size="xs" onClick={() => setLines(form.lines.filter((_: any, rowIndex: number) => rowIndex !== index))}>Remove</Button></td></tr>)}</tbody></table></div>
      {!sourceLocked && <Button variant="outline" onClick={() => setLines([...form.lines, blankLine()])}>Add Manual Line</Button>}
      <div className="grid gap-3 md:grid-cols-3"><label className="text-sm">Discount<CurrencyInput value={Number(form.discount_amount)} onValueChange={(value) => setForm({ ...form, discount_amount: value })} /></label><label className="text-sm">Tax<CurrencyInput value={Number(form.tax_amount)} onValueChange={(value) => setForm({ ...form, tax_amount: value })} /></label><label className="text-sm">Withholding Tax<CurrencyInput value={Number(form.withholding_tax_amount)} onValueChange={(value) => setForm({ ...form, withholding_tax_amount: value })} /></label></div>
      <div className="text-right text-lg font-semibold">Invoice Total: {money(total)}</div>
      <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-2" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button loading={save.isPending} onClick={submit}>Save Draft</Button></DialogFooter></DialogContent></Dialog>
  </>;
}

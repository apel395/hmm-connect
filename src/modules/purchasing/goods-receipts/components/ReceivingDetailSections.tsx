import { useId, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import DocumentActivity from "../../components/DocumentActivity";
import { destinationLabel } from "../destination";
import type { GoodsReceipt } from "../types";

type Section = "items" | "billing" | "approval" | "activity";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const approvalLabel = (role?: string) => ({
  STORE: "Store", CHEF: "Chef", "PM/CAMP BOSS": "PM / Camp Boss", PM: "PM / Camp Boss",
  "HO PURCHASING": "HO Purchasing", FINANCE: "Finance", "GENERAL MANAGER": "General Manager",
}[String(role ?? "").toUpperCase()] ?? role ?? "Approval");

export default function ReceivingDetailSections({ receipt }: { receipt: GoodsReceipt }) {
  const [section, setSection] = useState<Section>("items");
  const [search, setSearch] = useState("");
  const id = useId();
  const historical = receipt.source_type === "HISTORICAL_ENTRY";
  const tabs: { key: Section; label: string }[] = [
    { key: "items", label: "Received Items" },
    { key: "billing", label: "Supplier Billing" },
    ...(!historical ? [{ key: "approval" as const, label: "Approval" }] : []),
    { key: "activity", label: "Activity & Files" },
  ];
  const normalized = search.trim().toLowerCase();
  const items = normalized ? receipt.items.filter(item =>
    item.product_name.toLowerCase().includes(normalized) ||
    (item.product_code ?? "").toLowerCase().includes(normalized)
  ) : receipt.items;
  const showDestination = new Set(receipt.items.map(item =>
    destinationLabel(item.destination_type ?? receipt.destination_type, item.inventory_treatment)
  )).size > 1;
  const showTax = receipt.items.some(item => item.is_taxable || Number(item.tax_amount ?? 0) !== 0);
  const subtotal = Number(receipt.subtotal ?? receipt.items.reduce((sum, item) =>
    sum + Number(item.quantity) * Number(item.unit_cost), 0));
  const tax = Number(receipt.tax_amount ?? receipt.items.reduce((sum, item) =>
    sum + Number(item.tax_amount ?? 0), 0));
  const grandTotal = Number(receipt.total_amount ?? subtotal + tax);
  const approvalHistory = receipt.approval_history ?? [];

  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length :
      event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length :
      event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    setSection(tabs[next].key);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  };

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-slate-200 px-4 sm:px-6">
        <div role="tablist" aria-label="Receiving detail sections" className="flex gap-5 overflow-x-auto">
          {tabs.map((tab, index) => (
            <button type="button" role="tab" key={tab.key}
              id={id + "-" + tab.key + "-tab"}
              aria-controls={id + "-" + tab.key + "-panel"}
              aria-selected={section === tab.key}
              tabIndex={section === tab.key ? 0 : -1}
              onClick={() => setSection(tab.key)}
              onKeyDown={event => onTabKeyDown(event, index)}
              className={"shrink-0 border-b-2 py-4 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-emerald-600 " +
                (section === tab.key ? "border-emerald-700 text-emerald-800" :
                  "border-transparent text-slate-500 hover:text-slate-900")}>
              {tab.label}
              {tab.key === "items" && <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{receipt.items.length}</span>}
            </button>
          ))}
        </div>
      </div>
      <section role="tabpanel" id={id + "-" + section + "-panel"}
        aria-labelledby={id + "-" + section + "-tab"} tabIndex={0}>
        {section === "items" && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 p-4 sm:px-6">
              <div>
                <h2 className="font-semibold text-slate-900">Received Items</h2>
                <p className="text-xs text-slate-500">{items.length} of {receipt.items.length} items</p>
              </div>
              <label className="relative block w-full sm:w-72">
                <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <span className="sr-only">Search received items</span>
                <input type="search" value={search} onChange={event => setSearch(event.target.value)}
                  placeholder="Search item or code"
                  className="h-10 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" />
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm">
                <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr className="border-y border-slate-200">
                    <th scope="col" className="px-4 py-3 font-semibold sm:pl-6">Item</th>
                    {showDestination && <th scope="col" className="px-3 py-3 font-semibold">Destination</th>}
                    <th scope="col" className="px-3 py-3 text-right font-semibold">Qty / UOM</th>
                    <th scope="col" className="px-3 py-3 text-right font-semibold">Unit Cost</th>
                    {showTax && <th scope="col" className="px-3 py-3 text-right font-semibold">PPN</th>}
                    <th scope="col" className="px-4 py-3 text-right font-semibold sm:pr-6">Line Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map(item => {
                    const lineSubtotal = Number(item.line_subtotal ?? Number(item.quantity) * Number(item.unit_cost));
                    const lineTax = Number(item.tax_amount ?? 0);
                    return (
                      <tr key={item.id} className="hover:bg-slate-50/70">
                        <td className="px-4 py-3 sm:pl-6">
                          <div className="font-medium text-slate-800">{item.product_name}</div>
                          <div className="mt-0.5 text-xs text-slate-500">{item.product_code ?? "—"}</div>
                          {!showDestination && item.destination_override_reason &&
                            <div className="mt-1 text-xs text-amber-700">{item.destination_override_reason}</div>}
                        </td>
                        {showDestination && <td className="px-3 py-3 text-slate-600">
                          {destinationLabel(item.destination_type ?? receipt.destination_type, item.inventory_treatment)}
                          {item.destination_override_reason &&
                            <div className="max-w-44 text-xs text-amber-700">{item.destination_override_reason}</div>}
                        </td>}
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-slate-800">
                          {item.quantity} <span className="text-xs text-slate-500">{item.uom ?? "—"}</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-slate-600">{money(item.unit_cost)}</td>
                        {showTax && <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-slate-600">
                          {item.is_taxable ? <>{Number(item.tax_rate ?? 0)}% <span className="text-xs text-slate-500">({money(lineTax)})</span></> : "—"}
                        </td>}
                        <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-slate-900 sm:pr-6">
                          {money(item.line_total ?? lineSubtotal + lineTax)}
                        </td>
                      </tr>
                    );
                  })}
                  {items.length === 0 && <tr><td colSpan={4 + Number(showDestination) + Number(showTax)}
                    className="px-4 py-10 text-center text-slate-500">No items match your search.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end border-t border-slate-200 bg-slate-50/80 p-4 sm:px-6">
              <dl className="w-full max-w-sm space-y-2 text-sm">
                <div className="flex justify-between gap-8"><dt className="text-slate-500">Subtotal</dt><dd className="tabular-nums">{money(subtotal)}</dd></div>
                <div className="flex justify-between gap-8"><dt className="text-slate-500">PPN</dt><dd className="tabular-nums">{money(tax)}</dd></div>
                <div className="flex justify-between gap-8 border-t border-slate-200 pt-3 text-base">
                  <dt className="font-semibold">Receiving Total</dt>
                  <dd className="font-bold tabular-nums text-emerald-800">{money(grandTotal)}</dd>
                </div>
              </dl>
            </div>
          </>
        )}
        {section === "billing" && (
          <div className="space-y-6 p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="font-semibold">Supplier Billing</h2><p className="text-xs text-slate-500">Recorded supplier document details and additional charges</p></div>
              {receipt.supplier_invoice_status && <Badge variant={receipt.supplier_invoice_status === "DRAFT" ? "warning" : "success"}>{receipt.supplier_invoice_status}</Badge>}
            </div>
            <dl className="grid gap-x-8 gap-y-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <Detail label="Supplier Invoice Number">{receipt.supplier_invoice_number || "Not yet provided"}</Detail>
              <Detail label="Supplier Invoice Date">{receipt.supplier_invoice_date || "—"}</Detail>
              <Detail label="Supplier Document Total">{receipt.supplier_document_total == null ? "—" : money(receipt.supplier_document_total)}</Detail>
              <Detail label="Invoice Discount">{money(receipt.discount_amount)}</Detail>
              <Detail label="Shipping Fee">{money(receipt.shipping_fee_amount)}</Detail>
              <Detail label="Administration Fee">{money(receipt.admin_fee_amount)}</Detail>
              <Detail label="Other Fee">{money(receipt.other_fee_amount)}</Detail>
              <Detail label="Other Fee Description">{receipt.other_fee_description || "—"}</Detail>
              <Detail label="Supplier Invoice Status">{receipt.supplier_invoice_status || "Not generated yet"}</Detail>
            </dl>
            {receipt.supplier_invoice_id && <Link className="inline-flex text-sm font-semibold text-emerald-700 hover:underline"
              to={"/supplier-invoices/" + receipt.supplier_invoice_id}>Open linked supplier invoice</Link>}
            {receipt.supplier_document_url && <a className="block text-sm font-medium text-emerald-700 underline"
              href={receipt.supplier_document_url} target="_blank" rel="noopener noreferrer">Open supplier document</a>}
            <div className="border-t border-slate-200 pt-4">
              <h3 className="mb-2 text-sm font-semibold">Receiving Notes</h3>
              <p className="whitespace-pre-wrap text-sm text-slate-600">{receipt.notes || "No notes provided."}</p>
            </div>
          </div>
        )}
        {section === "approval" && !historical && (
          <div className="space-y-4 p-4 sm:p-6">
            <div><h2 className="font-semibold">Approval Timeline</h2><p className="text-xs text-slate-500">Review stages and decisions for this Receiving</p></div>
            {approvalHistory.length === 0 ? <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">Not submitted for approval yet.</p> :
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {approvalHistory.map((step, index) => (
                  <div key={step.id ?? index} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div><p className="text-xs text-slate-500">Stage {step.level ?? step.step_order ?? index + 1}</p>
                        <p className="font-semibold">{approvalLabel(step.approver_role ?? step.approver_role_name ?? step.name)}</p></div>
                      <Badge variant={step.status === "APPROVED" ? "success" : step.status === "REJECTED" ? "danger" : "warning"}>{step.status}</Badge>
                    </div>
                    {step.approver_name && <p className="mt-2 text-xs text-slate-600">By {step.approver_name}</p>}
                    {step.decided_at && <p className="mt-1 text-xs text-slate-500">{new Date(step.decided_at).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })} WIB</p>}
                    {step.comment && <p className="mt-3 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">{step.comment}</p>}
                  </div>
                ))}
              </div>}
          </div>
        )}
        {section === "activity" && (
          <div className="space-y-5 bg-slate-50/50 p-4 sm:p-6">
            {receipt.allowed_actions?.can_manage_attachments !== false &&
              <DocumentAttachments entityType="GOODS_RECEIPT" entityId={receipt.id} />}
            {receipt.allowed_actions?.can_view_history !== false &&
              <div className="[&>div]:p-5"><DocumentActivity events={receipt.activity_history} /></div>}
          </div>
        )}
      </section>
    </Card>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="mb-1 text-xs text-slate-500">{label}</dt><dd className="font-medium text-slate-800">{children}</dd></div>;
}

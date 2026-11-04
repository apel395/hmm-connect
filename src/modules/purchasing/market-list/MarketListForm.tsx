import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import FormDialog from "@/components/form-system/FormDialog";
import FormErrorSummary from "@/components/form-system/FormErrorSummary";
import FormFooter from "@/components/form-system/FormFooter";
import FormGrid from "@/components/form-system/FormGrid";
import FormSection from "@/components/form-system/FormSection";
import Button from "@/components/ui/Button";
import { Trash2 } from "lucide-react";
import Textarea from "@/components/ui/Textarea";
import SearchableSelect from "@/components/form/SearchableSelect";
import ProductCombobox from "@/components/form/ProductCombobox";
import CurrencyInput from "@/components/form/CurrencyInput";
import QuantityInput from "@/components/form/QuantityInput";
import Badge from "@/components/ui/Badge";
import {
  filterBusinessUnits,
  listDepartments,
  listLocations,
} from "@/modules/admin/organization/api";
import { isBeforeDate, todayLocal } from "@/utils/dateConstraints";
import useFormRecovery from "@/hooks/useFormRecovery";
import useUnsavedFormChanges from "@/hooks/useUnsavedFormChanges";
import focusFormField from "@/utils/focusFormField";
import {
  initialMarketListDraft,
  validMarketListDraft,
  type MarketListDraft,
  type MarketListProduct as Product,
  type MarketListRow as Row,
} from "./marketListDraft";

export default function MarketListForm({
  onClose,
  onSubmit,
  initialData,
}: {
  onClose: () => void;
  onSubmit: (payload: any) => Promise<void>;
  initialData?: any;
}) {
  const editing = Boolean(initialData);
  const [bu, setBu] = useState<number>();
  const [dept, setDept] = useState<number>();
  const [loc, setLoc] = useState<number>();
  const [requestDate, setRequestDate] = useState(todayLocal());
  const [expiry, setExpiry] = useState("");
  const [notes, setNotes] = useState("");
  const [notesOpen, setNotesOpen] = useState(false);
  const [rows, setRows] = useState<Row[]>([
    { product_id: 0, quantity: 1, estimated_price: 0 },
  ]);
  const [products, setProducts] = useState<Product[]>([]);
  const [saving, setSaving] = useState(false);
  const [ready, setReady] = useState(false);
  const [formError, setFormError] = useState("");
  const originalSnapshot = useRef("");
  const draft: MarketListDraft = {
    bu,
    dept,
    loc,
    requestDate,
    expiry,
    notes,
    rows,
    products,
  };
  const dirty = ready && JSON.stringify(draft) !== originalSnapshot.current;
  const recovery = useFormRecovery<MarketListDraft>(
    editing ? `market-list:edit:${initialData.id}` : "market-list:create",
    draft,
    dirty,
    validMarketListDraft,
  );
  const requestClose = useUnsavedFormChanges({
    dirty,
    busy: saving,
    recoverable: !recovery.failed,
    onClose,
  });
  const bus = useQuery({
    queryKey: ["business-units", "ml-form"],
    queryFn: () => filterBusinessUnits({ is_active: true }),
  });
  const departments = useQuery({
    queryKey: ["departments", "ml-form", bu],
    queryFn: () => listDepartments({ business_unit_id: bu, is_active: true }),
    enabled: Boolean(bu),
  });
  const locations = useQuery({
    queryKey: ["locations", "ml-form", bu],
    queryFn: () =>
      listLocations({
        business_unit_id: bu,
        is_active: true,
        assigned_only: true,
      }),
    enabled: Boolean(bu),
  });
  useEffect(() => {
    if (ready) return;
    const original = initialMarketListDraft(initialData);
    const saved = recovery.load();
    const next = saved ?? original;
    originalSnapshot.current = JSON.stringify(original);
    setBu(next.bu);
    setDept(next.dept);
    setLoc(next.loc);
    setRequestDate(next.requestDate);
    setExpiry(next.expiry);
    setNotes(next.notes);
    setRows(next.rows);
    setProducts(next.products);
    setReady(true);
    if (saved) recovery.notifyRestored();
  }, [initialData, ready, recovery]);
  useEffect(() => {
    if (ready && !dirty) recovery.clear();
  }, [ready, dirty, recovery]);
  useEffect(() => {
    if (ready && notes.trim()) setNotesOpen(true);
  }, [ready, notes]);
  const totals = useMemo(
    () =>
      rows.reduce(
        (a, r) => {
          const p = products.find((x) => x.id === r.product_id);
          const sub = r.quantity * r.estimated_price;
          const tax = p?.is_taxable ? (sub * Number(p.tax_rate || 0)) / 100 : 0;
          return {
            subtotal: a.subtotal + sub,
            tax: a.tax + tax,
            total: a.total + sub + tax,
          };
        },
        { subtotal: 0, tax: 0, total: 0 },
      ),
    [rows, products],
  );
  const remember = (p: Product) =>
    setProducts((c) =>
      c.some((x) => x.id === p.id)
        ? c.map((x) => (x.id === p.id ? { ...x, ...p } : x))
        : [...c, p],
    );
  const money = (n: number) =>
    n.toLocaleString("id-ID", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  const selectMarketItem = (index: number, p: Product) => {
    remember(p);
    const history =
      p.last_purchase_price === null || p.last_purchase_price === undefined
        ? null
        : Number(p.last_purchase_price);
    setRows((current) =>
      current.map((row, j) =>
        j === index
          ? {
              ...row,
              product_id: p.id,
              estimated_price:
                history !== null && Number.isFinite(history)
                  ? history
                  : row.estimated_price,
            }
          : row,
      ),
    );
  };
  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (saving) return;
    const bad = rows.some(
      (r) => r.product_id && (r.quantity <= 0 || r.estimated_price <= 0),
    );
    const valid = rows.filter(
      (r) => r.product_id && r.quantity > 0 && r.estimated_price > 0,
    );
    const validation = !bu
      ? {
          message: "Business Unit, Department and Location are required.",
          field: "business-unit",
        }
      : !dept
        ? {
            message: "Business Unit, Department and Location are required.",
            field: "department",
          }
        : !loc
          ? {
              message: "Business Unit, Department and Location are required.",
              field: "location",
            }
          : !requestDate
            ? { message: "Request Date is required.", field: "request-date" }
            : expiry && isBeforeDate(expiry, requestDate)
              ? {
                  message: "Valid Until cannot be before Request Date.",
                  field: "expiry-date",
                }
              : !valid.length
                ? {
                    message: bad
                      ? "Quantity and estimated price must be greater than zero."
                      : "Add at least one market item.",
                    field: "items",
                  }
                : null;
    if (validation) {
      setFormError(validation.message);
      focusFormField(validation.field);
      return;
    }
    setFormError("");
    setSaving(true);
    try {
      await onSubmit({
        business_unit_id: bu,
        department_id: dept,
        location_id: loc,
        request_date: requestDate,
        expiry_date: expiry || null,
        notes,
        items: valid,
      });
      recovery.clear();
      onClose();
    } catch {
      setFormError(
        "Market List could not be saved. Your input is still available here.",
      );
    } finally {
      setSaving(false);
    }
  }
  const discard = () => {
    if (
      !window.confirm(
        "Discard unfinished Market List input stored in this browser?",
      )
    )
      return;
    recovery.clear();
    onClose();
  };
  return (
    <FormDialog
      open
      size="large"
      busy={saving}
      title={editing ? "Edit Market List" : "Create Market List"}
      description="Market items follow Item Master eligibility; previous purchase price supplies the initial estimate."
      onRequestClose={requestClose}
      footer={
        <FormFooter
          onCancel={requestClose}
          onSubmit={() => {
            void submit();
          }}
          submitLabel={editing ? "Save Changes" : "Create Market List"}
          saving={saving}
          aside={
            dirty ? (
              <div className="flex flex-wrap items-center gap-2">
                <span
                  role="status"
                  className={
                    recovery.failed ? "text-red-700" : "text-emerald-700"
                  }
                >
                  {recovery.failed
                    ? "Browser recovery unavailable"
                    : "Input saved in this browser"}
                </span>
                <button
                  type="button"
                  disabled={saving}
                  className="text-xs font-medium text-slate-600 underline hover:text-red-700"
                  onClick={discard}
                >
                  Discard input
                </button>
              </div>
            ) : null
          }
        />
      }
    >
      {!ready ? (
        <p className="py-6 text-center text-sm text-slate-500">
          Preparing market list…
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <FormErrorSummary message={formError} />
          <FormSection title="Request Information">
            <FormGrid columns={3}>
              <label
                data-form-field="business-unit"
                className="text-xs font-medium"
              >
                Business Unit
                <SearchableSelect
                  className="mt-1"
                  value={bu}
                  options={bus.data ?? []}
                  onChange={(id) => {
                    setBu(id || undefined);
                    setDept(undefined);
                    setLoc(undefined);
                  }}
                />
              </label>
              <label
                data-form-field="department"
                className="text-xs font-medium"
              >
                Department
                <SearchableSelect
                  className="mt-1"
                  value={dept}
                  options={departments.data ?? []}
                  disabled={!bu}
                  onChange={(id) => setDept(id || undefined)}
                />
              </label>
              <label data-form-field="location" className="text-xs font-medium">
                Location
                <SearchableSelect
                  className="mt-1"
                  value={loc}
                  options={locations.data ?? []}
                  disabled={!bu}
                  onChange={(id) => setLoc(id || undefined)}
                />
              </label>
              <label
                data-form-field="request-date"
                className="text-xs font-medium"
              >
                Request Date
                <input
                  className="mt-1 h-10 w-full rounded border px-3"
                  type="date"
                  data-accounting-date="true"
                  value={requestDate}
                  onChange={(e) => setRequestDate(e.target.value)}
                />
              </label>
              <label
                data-form-field="expiry-date"
                className="text-xs font-medium"
              >
                Valid Until
                <input
                  className="mt-1 h-10 w-full rounded border px-3"
                  type="date"
                  min={editing ? undefined : requestDate}
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                />
              </label>
            </FormGrid>
            <details
              open={notesOpen}
              onToggle={(event) => setNotesOpen(event.currentTarget.open)}
              className="rounded-md border border-slate-200 px-3 py-2"
            >
              <summary className="cursor-pointer text-xs font-medium text-slate-700">
                Purpose / Notes (optional)
              </summary>
              <Textarea
                className="mt-2"
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Purpose / notes"
              />
            </details>
          </FormSection>
          <FormSection title="Market Items">
            <div
              data-form-field="items"
              className="overflow-x-auto rounded border"
            >
              <table className="w-full min-w-[860px] table-fixed text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="w-[30%] p-2 text-left">Market Item</th>
                    <th className="w-[8%] p-2 text-left">UOM</th>
                    <th className="w-[12%] p-2 text-right">Qty</th>
                    <th className="w-[20%] p-2 text-right">Estimated Price</th>
                    <th className="w-[16%] p-2 text-right">Line Total</th>
                    <th className="w-[10%] p-2 text-left">Tax</th>
                    <th className="w-[4%]" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const p = products.find((x) => x.id === r.product_id);
                    const sub = r.quantity * r.estimated_price;
                    const tax = p?.is_taxable
                      ? (sub * Number(p.tax_rate || 0)) / 100
                      : 0;
                    return (
                      <tr key={i} className="border-t">
                        <td className="p-2">
                          <ProductCombobox
                            remote
                            marketOnly
                            value={r.product_id || undefined}
                            products={products}
                            onChange={(id) =>
                              setRows((x) =>
                                x.map((v, j) =>
                                  j === i ? { ...v, product_id: id } : v,
                                ),
                              )
                            }
                            onSelect={(s) => selectMarketItem(i, s as Product)}
                          />
                        </td>
                        <td className="p-2">{p?.uom ?? "—"}</td>
                        <td className="p-2">
                          <QuantityInput
                            value={r.quantity}
                            min={0.01}
                            onValueChange={(v) =>
                              setRows((x) =>
                                x.map((a, j) =>
                                  j === i ? { ...a, quantity: v } : a,
                                ),
                              )
                            }
                          />
                        </td>
                        <td className="p-2">
                          <CurrencyInput
                            value={r.estimated_price}
                            onValueChange={(v) =>
                              setRows((x) =>
                                x.map((a, j) =>
                                  j === i ? { ...a, estimated_price: v } : a,
                                ),
                              )
                            }
                          />
                          {p?.last_purchase_price !== null &&
                          p?.last_purchase_price !== undefined ? (
                            <div className="mt-1 text-[11px] text-slate-500">
                              Last PO: Rp {money(Number(p.last_purchase_price))}
                            </div>
                          ) : null}
                        </td>
                        <td className="p-2 text-right tabular-nums">
                          <div className="font-semibold">
                            {money(sub + tax)}
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500">
                            Base {money(sub)} · PPN {money(tax)}
                          </div>
                        </td>
                        <td className="p-2">
                          {p?.tax_category === "REVIEW_REQUIRED" ? (
                            <Badge variant="warning">Review</Badge>
                          ) : p?.is_taxable ? (
                            <Badge variant="info">
                              PPN {Number(p.tax_rate || 0)}%
                            </Badge>
                          ) : (
                            <Badge variant="secondary">Non PPN</Badge>
                          )}
                        </td>
                        <td className="p-1 text-center">
                          <button
                            type="button"
                            disabled={rows.length === 1}
                            aria-label="Remove market item"
                            title="Remove item"
                            className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-30"
                            onClick={() =>
                              setRows((x) => x.filter((_, j) => j !== i))
                            }
                          >
                            <Trash2 aria-hidden="true" className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <Button
                type="button"
                onClick={() =>
                  setRows((x) => [
                    ...x,
                    { product_id: 0, quantity: 1, estimated_price: 0 },
                  ])
                }
              >
                Add Item
              </Button>
              <div className="w-full rounded border bg-slate-50 px-4 py-3 text-sm sm:w-auto sm:min-w-72">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <b>{money(totals.subtotal)}</b>
                </div>
                <div className="flex justify-between">
                  <span>PPN</span>
                  <b>{money(totals.tax)}</b>
                </div>
                <div className="mt-2 flex justify-between border-t pt-2 text-base">
                  <span>Total</span>
                  <b>{money(totals.total)}</b>
                </div>
              </div>
            </div>
          </FormSection>
        </form>
      )}
    </FormDialog>
  );
}

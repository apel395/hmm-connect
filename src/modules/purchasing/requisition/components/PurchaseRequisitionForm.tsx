import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import FormDialog from "@/components/form-system/FormDialog";
import FormErrorSummary from "@/components/form-system/FormErrorSummary";
import FormFooter from "@/components/form-system/FormFooter";
import FormGrid from "@/components/form-system/FormGrid";
import FormSection from "@/components/form-system/FormSection";
import Textarea from "@/components/ui/Textarea";
import SearchableSelect from "@/components/form/SearchableSelect";
import useFormRecovery from "@/hooks/useFormRecovery";
import useUnsavedFormChanges from "@/hooks/useUnsavedFormChanges";
import focusFormField from "@/utils/focusFormField";
import {
  filterBusinessUnits,
  listDepartments,
  listLocations,
} from "@/modules/admin/organization/api";
import { isBeforeDate, todayLocal } from "@/utils/dateConstraints";
import { useAuthStore } from "@/store/auth";

import PurchaseRequisitionItems, {
  type PurchaseRequisitionItemRow,
  type Product,
} from "./PurchaseRequisitionItems";
import {
  initialPurchaseRequisitionDraft,
  validPurchaseRequisitionDraft,
  type PurchaseRequisitionDraft,
} from "./purchaseRequisitionDraft";

interface Props {
  onClose: () => void;
  onSubmit: (payload: any) => Promise<void>;
  initialData?: any;
}

export default function PurchaseRequisitionForm({
  onClose,
  onSubmit,
  initialData,
}: Props) {
  const editing = Boolean(initialData);
  const user = useAuthStore((state) => state.user);
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [notes, setNotes] = useState("");
  const [notesOpen, setNotesOpen] = useState(false);
  const [expiryDate, setExpiryDate] = useState("");
  const [requestDate, setRequestDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [items, setItems] = useState<PurchaseRequisitionItemRow[]>([
    { product_id: 0, quantity: 1, estimated_price: 0 },
  ]);
  const [ready, setReady] = useState(false);
  const originalSnapshot = useRef("");
  const draft: PurchaseRequisitionDraft = {
    businessUnitId,
    departmentId,
    locationId,
    notes,
    expiryDate,
    requestDate,
    products,
    items,
  };
  const dirty = ready && JSON.stringify(draft) !== originalSnapshot.current;
  const recovery = useFormRecovery<PurchaseRequisitionDraft>(
    editing
      ? `purchase-requisition:edit:${initialData.id}`
      : "purchase-requisition:create",
    draft,
    dirty,
    validPurchaseRequisitionDraft,
  );
  const requestClose = useUnsavedFormChanges({
    dirty,
    busy: saving,
    recoverable: !recovery.failed,
    onClose,
  });

  const businessUnits = useQuery({
    queryKey: ["business-units", "pr-form"],
    queryFn: () => filterBusinessUnits({ is_active: true }),
  });
  const departments = useQuery({
    queryKey: ["departments", "pr-form", businessUnitId, locationId],
    queryFn: () =>
      listDepartments({
        business_unit_id: businessUnitId,
        location_id: locationId,
        is_active: true,
      }),
    enabled: Boolean(businessUnitId && locationId),
  });
  const locations = useQuery({
    queryKey: ["locations", "pr-form", businessUnitId],
    queryFn: () =>
      listLocations({
        business_unit_id: businessUnitId,
        is_active: true,
        assigned_only: true,
      }),
    enabled: Boolean(businessUnitId),
  });
  const activeDepartments = useMemo(
    () => departments.data ?? [],
    [departments.data],
  );
  const activeLocations = useMemo(() => locations.data ?? [], [locations.data]);

  useEffect(() => {
    if (!ready) return;
    if (!editing && !departmentId && activeDepartments.length === 1) {
      setDepartmentId(activeDepartments[0].id);
    }
  }, [activeDepartments, departmentId, editing, ready]);

  useEffect(() => {
    if (!ready) return;
    if (!editing && !locationId && activeLocations.length === 1) {
      setLocationId(activeLocations[0].id);
    }
  }, [activeLocations, locationId, editing, ready]);

  useEffect(() => {
    if (ready) return;
    const original = initialPurchaseRequisitionDraft(initialData, user);
    const saved = recovery.load();
    const next = saved ?? original;
    originalSnapshot.current = JSON.stringify(original);
    setBusinessUnitId(next.businessUnitId);
    setDepartmentId(next.departmentId);
    setLocationId(next.locationId);
    setNotes(next.notes);
    setExpiryDate(next.expiryDate);
    setRequestDate(next.requestDate);
    setProducts(next.products);
    setItems(next.items);
    setReady(true);
    if (saved) recovery.notifyRestored();
  }, [initialData, user, ready, recovery]);
  useEffect(() => {
    if (ready && !dirty) recovery.clear();
  }, [ready, dirty, recovery]);
  useEffect(() => {
    if (ready && notes.trim()) setNotesOpen(true);
  }, [ready, notes]);

  function rememberProduct(product: Product) {
    setProducts((current) =>
      current.some((item) => item.id === product.id)
        ? current.map((item) =>
            item.id === product.id ? { ...item, ...product } : item,
          )
        : [...current, product],
    );
  }

  function changeBusinessUnit(id?: number) {
    setBusinessUnitId(id);
    setLocationId(undefined);
    setDepartmentId(undefined);
  }

  function changeLocation(id?: number) {
    setLocationId(id);
    setDepartmentId(undefined);
  }

  async function handleSubmit(event?: React.FormEvent) {
    event?.preventDefault();
    if (saving) return;
    const validItems = items.filter(
      (item) =>
        item.product_id > 0 && item.quantity > 0 && item.estimated_price > 0,
    );
    const badPrice = items.some(
      (item) =>
        item.product_id > 0 &&
        (item.quantity <= 0 || item.estimated_price <= 0),
    );
    const validation = !businessUnitId
      ? { message: "Business Unit is required.", field: "business-unit" }
      : !departmentId
        ? { message: "Department is required.", field: "department" }
        : !locationId
          ? { message: "Location is required.", field: "location" }
          : !requestDate
            ? { message: "Request Date is required.", field: "request-date" }
            : !editing &&
                expiryDate &&
                isBeforeDate(expiryDate, requestDate || todayLocal())
              ? {
                  message: "Valid Until cannot be before Request Date.",
                  field: "expiry-date",
                }
              : !validItems.length
                ? {
                    message: badPrice
                      ? "Estimated price and quantity must be greater than zero."
                      : "Please add valid products.",
                    field: "items",
                  }
                : null;
    if (validation) {
      setFormError(validation.message);
      focusFormField(validation.field);
      return;
    }
    setFormError("");
    try {
      setSaving(true);
      await onSubmit({
        business_unit_id: businessUnitId,
        department_id: departmentId,
        location_id: locationId,
        request_date: requestDate || undefined,
        notes,
        expiry_date: expiryDate || null,
        items: validItems,
      });
      recovery.clear();
      onClose();
    } catch {
      setFormError(
        "Purchase Requisition could not be saved. Your input is still available here.",
      );
    } finally {
      setSaving(false);
    }
  }
  const discard = () => {
    if (
      !window.confirm(
        "Discard unfinished Purchase Requisition input stored in this browser?",
      )
    )
      return;
    recovery.clear();
    onClose();
  };

  const lockedBusinessUnit =
    !editing &&
    Boolean(user?.business_unit_id ?? user?.default_business_unit_id);
  const lockedDepartment =
    !editing && Boolean(user?.department_id ?? user?.default_department_id);
  const lockedLocation =
    !editing && Boolean(user?.location_id ?? user?.default_location_id);
  const fieldClass =
    "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

  return (
    <FormDialog
      open
      size="large"
      busy={saving}
      title={
        editing ? "Edit Purchase Requisition" : "Create Purchase Requisition"
      }
      description={
        editing
          ? "Update requisition details without changing its number."
          : "Create a purchasing request before approval and ordering."
      }
      onRequestClose={requestClose}
      footer={
        <FormFooter
          onCancel={requestClose}
          onSubmit={() => {
            void handleSubmit();
          }}
          submitLabel={editing ? "Save Changes" : "Create Purchase Requisition"}
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
          Preparing purchase requisition…
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
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
                  value={businessUnitId}
                  options={businessUnits.data ?? []}
                  disabled={lockedBusinessUnit}
                  placeholder="Type business unit..."
                  onChange={(id) => changeBusinessUnit(id || undefined)}
                />
              </label>
              <label data-form-field="location" className="text-xs font-medium">
                Location
                <SearchableSelect
                  className="mt-1"
                  value={locationId}
                  options={activeLocations}
                  disabled={
                    lockedLocation || !businessUnitId || locations.isLoading
                  }
                  placeholder="Type location..."
                  onChange={(id) => changeLocation(id || undefined)}
                />
              </label>
              <label
                data-form-field="department"
                className="text-xs font-medium"
              >
                Department
                <SearchableSelect
                  className="mt-1"
                  value={departmentId}
                  options={activeDepartments}
                  disabled={
                    lockedDepartment || !locationId || departments.isLoading
                  }
                  placeholder="Type department..."
                  onChange={(id) => setDepartmentId(id || undefined)}
                />
              </label>
              <label
                data-form-field="request-date"
                className="text-xs font-medium"
              >
                Request Date
                <input
                  type="date"
                  data-accounting-date="true"
                  value={requestDate}
                  onChange={(e) => setRequestDate(e.target.value)}
                  className={fieldClass}
                />
              </label>
              <label
                data-form-field="expiry-date"
                className="text-xs font-medium"
              >
                Valid Until
                <input
                  type="date"
                  min={requestDate || undefined}
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className={fieldClass}
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
              />
            </details>
          </FormSection>
          <FormSection title="Requested Items">
            <div data-form-field="items">
              <PurchaseRequisitionItems
                items={items}
                products={products}
                onChange={setItems}
                onProductLoaded={rememberProduct}
              />
            </div>
          </FormSection>
        </form>
      )}
    </FormDialog>
  );
}

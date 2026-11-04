import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import FormDialog from "@/components/form-system/FormDialog";
import FormErrorSummary from "@/components/form-system/FormErrorSummary";
import FormFooter from "@/components/form-system/FormFooter";
import FormSection from "@/components/form-system/FormSection";
import useFormRecovery from "@/hooks/useFormRecovery";
import useUnsavedFormChanges from "@/hooks/useUnsavedFormChanges";
import focusFormField from "@/utils/focusFormField";
import {
  filterBusinessUnits,
  listDepartments,
  listLocations,
} from "@/modules/admin/organization/api";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { useSupplierProducts } from "@/modules/master/suppliers/hooks/useSupplierProducts";
import { isBeforeDate, todayLocal } from "@/utils/dateConstraints";
import { marketListApi } from "@/modules/purchasing/market-list/marketListApi";
import { useApprovedPurchaseRequisitions } from "../hooks/usePurchaseOrders";
import PurchaseOrderHeader from "./PurchaseOrderHeader";
import PurchaseOrderItems, {
  type PurchaseOrderItemRow,
} from "./PurchaseOrderItems";
import PurchaseOrderSummary from "./PurchaseOrderSummary";
import type { MarketListOption } from "./MarketListPicker";
import {
  initialPurchaseOrderDraft,
  validPurchaseOrderDraft,
  type PurchaseOrderDraft,
  type CreationType,
  type ProductOption,
} from "./purchaseOrderDraft";

interface Props {
  open: boolean;
  loading?: boolean;
  onClose: () => void;
  onSubmit: (payload: any) => Promise<boolean | void> | boolean | void;
  initialData?: any;
}
export default function PurchaseOrderForm({
  open,
  loading,
  onClose,
  onSubmit,
  initialData,
}: Props) {
  const editing = Boolean(initialData);
  const { data: suppliers = [] } = useSuppliers("", 50, open);
  const { data: approvedPRs = [] } = useApprovedPurchaseRequisitions();
  const { data: approvedMLs = [] } = useQuery({
    queryKey: ["approved-market-lists-for-po"],
    queryFn: async () =>
      (
        await marketListApi.list({
          scope: "active",
          status: "APPROVED",
          page: 1,
          page_size: 100,
        })
      ).data.items ?? [],
    enabled: open && !editing,
  });
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [creationType, setCreationType] = useState<CreationType>("FROM_PR");
  const [supplierId, setSupplierId] = useState<number>();
  const [selectedPRs, setSelectedPRs] = useState<any[]>([]);
  const [selectedML, setSelectedML] = useState<MarketListOption>();
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [orderDate, setOrderDate] = useState(todayLocal());
  const [expectedDate, setExpectedDate] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState("");
  const [items, setItems] = useState<PurchaseOrderItemRow[]>([]);
  const [ready, setReady] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const originalSnapshot = useRef("");
  const restoredMarketListId = useRef<number | null>(null);
  const draft: PurchaseOrderDraft = {
    creationType,
    supplierId,
    selectedPRs,
    selectedML,
    businessUnitId,
    departmentId,
    locationId,
    orderDate,
    expectedDate,
    notes,
    products,
    items,
  };
  const dirty =
    open && ready && JSON.stringify(draft) !== originalSnapshot.current;
  const busy = Boolean(loading || submitting);
  const recovery = useFormRecovery<PurchaseOrderDraft>(
    editing ? `purchase-order:edit:${initialData.id}` : "purchase-order:create",
    draft,
    dirty,
    validPurchaseOrderDraft,
  );
  const requestClose = useUnsavedFormChanges({
    dirty,
    busy,
    recoverable: !recovery.failed,
    onClose,
  });
  const { data: marketListDetail } = useQuery({
    queryKey: ["purchase-order-source-market-list", selectedML?.id],
    queryFn: async () => (await marketListApi.detail(selectedML!.id)).data,
    enabled:
      open && !editing && creationType === "FROM_ML" && Boolean(selectedML?.id),
  });
  const { data: supplierProducts = [] } = useSupplierProducts(supplierId);
  const businessUnits = useQuery({
    queryKey: ["business-units", "po-form"],
    queryFn: () => filterBusinessUnits({ is_active: true }),
    enabled: open,
  });
  const departments = useQuery({
    queryKey: ["departments", "po-form", businessUnitId],
    queryFn: () =>
      listDepartments({ business_unit_id: businessUnitId, is_active: true }),
    enabled: open && Boolean(businessUnitId),
  });
  const locations = useQuery({
    queryKey: ["locations", "po-form", businessUnitId],
    queryFn: () =>
      listLocations({
        business_unit_id: businessUnitId,
        is_active: true,
        assigned_only: true,
      }),
    enabled: open && Boolean(businessUnitId),
  });
  useEffect(() => {
    if (!open) {
      setReady(false);
      return;
    }
    if (ready) return;
    const original = initialPurchaseOrderDraft(initialData);
    const saved = recovery.load();
    const next = saved ?? original;
    originalSnapshot.current = JSON.stringify(original);
    restoredMarketListId.current = saved?.selectedML?.id ?? null;
    setCreationType(next.creationType);
    setSupplierId(next.supplierId);
    setSelectedPRs(next.selectedPRs);
    setSelectedML(next.selectedML);
    setBusinessUnitId(next.businessUnitId);
    setDepartmentId(next.departmentId);
    setLocationId(next.locationId);
    setOrderDate(next.orderDate);
    setExpectedDate(next.expectedDate);
    setNotes(next.notes);
    setProducts(next.products);
    setItems(next.items);
    setFormError("");
    setReady(true);
    if (saved) recovery.notifyRestored();
  }, [open, ready, initialData, recovery]);
  useEffect(() => {
    if (open && ready && !dirty) recovery.clear();
  }, [open, ready, dirty, recovery]);
  useEffect(() => {
    if (!open || !ready || !marketListDetail || creationType !== "FROM_ML")
      return;
    if (restoredMarketListId.current === marketListDetail.id) {
      return;
    }
    setSelectedML((current) =>
      current?.id === marketListDetail.id
        ? { ...current, ...marketListDetail }
        : current,
    );
    setBusinessUnitId(marketListDetail.business_unit_id ?? undefined);
    setDepartmentId(marketListDetail.department_id ?? undefined);
    setLocationId(marketListDetail.location_id ?? undefined);
    setNotes(marketListDetail.notes ?? "");
    setItems(
      (marketListDetail.items ?? [])
        .filter((item: any) => Number(item.quantity) > 0)
        .map((item: any) => ({
          product_id: item.product_id,
          product_code: item.product_code,
          product_name: item.product_name,
          description: item.product_description ?? "",
          uom: item.uom,
          requested_quantity: Number(item.quantity),
          remaining_quantity: Number(item.remaining_quantity ?? item.quantity),
          quantity: Number(item.remaining_quantity ?? item.quantity),
          unit_price: Number(item.estimated_price),
          purchase_requisition_item_id: null,
          market_list_item_id: item.id,
          source_ml_number: marketListDetail.ml_number,
        })),
    );
  }, [marketListDetail, creationType, open, ready]);
  useEffect(() => {
    if (!open || !ready || !supplierProducts.length) return;
    setItems((current) =>
      current.map((item) => {
        if (item.unit_price !== 0) return item;
        const match = supplierProducts.find(
          (entry: any) =>
            entry.product_id === item.product_id &&
            entry.is_active &&
            Number(entry.last_price) > 0,
        );
        return match ? { ...item, unit_price: Number(match.last_price) } : item;
      }),
    );
  }, [supplierProducts, open, ready]);
  const availablePRs = useMemo(() => {
    const ids = new Set(approvedPRs.map((item: any) => item.id));
    return [
      ...selectedPRs.filter((item: any) => !ids.has(item.id)),
      ...approvedPRs,
    ];
  }, [approvedPRs, selectedPRs]);
  const changeType = (type: CreationType) => {
    if (editing) return;
    restoredMarketListId.current = null;
    setCreationType(type);
    setSelectedPRs([]);
    setSelectedML(undefined);
    setBusinessUnitId(undefined);
    setDepartmentId(undefined);
    setLocationId(undefined);
    setItems([]);
  };
  const changeBusinessUnit = (id?: number) => {
    setBusinessUnitId(id);
    setDepartmentId(undefined);
    setLocationId(undefined);
  };
  const selectPRs = (requisitions: any[]) => {
    const first = requisitions[0];
    const existing = new Map(
      items
        .filter((item) => item.purchase_requisition_item_id)
        .map((item) => [item.purchase_requisition_item_id, item]),
    );
    setSelectedPRs(requisitions);
    setBusinessUnitId(first?.business_unit_id ?? undefined);
    setDepartmentId(first?.department_id ?? undefined);
    setLocationId(first?.location_id ?? undefined);
    if (requisitions.length === 1) setNotes(requisitions[0]?.notes ?? "");
    setItems(
      requisitions.flatMap((requisition: any) =>
        (requisition.items ?? [])
          .filter((item: any) => Number(item.remaining_quantity) > 0)
          .map((item: any) => {
            const current = existing.get(item.id);
            return {
              product_id: item.product_id,
              product_code: item.product_code,
              product_name: item.product_name,
              description: item.description ?? item.remark ?? "",
              uom: item.uom,
              requested_quantity: Number(item.quantity),
              remaining_quantity: Number(item.remaining_quantity),
              quantity: current?.quantity ?? Number(item.remaining_quantity),
              unit_price:
                current?.unit_price ?? Number(item.estimated_price ?? 0),
              purchase_requisition_item_id: item.id,
              market_list_item_id: null,
              source_pr_number: requisition.pr_number,
            };
          }),
      ),
    );
  };
  const selectML = (marketList?: MarketListOption) => {
    restoredMarketListId.current = null;
    setSelectedML(marketList);
    setSelectedPRs([]);
    setItems([]);
  };
  const total = useMemo(
    () => items.reduce((sum, item) => sum + item.quantity * item.unit_price, 0),
    [items],
  );
  const save = async () => {
    if (busy) return;
    const validation = !supplierId
      ? "Supplier is required."
      : creationType === "FROM_PR" && !selectedPRs.length
        ? "Select at least one approved purchase requisition."
        : creationType === "FROM_ML" && !selectedML
          ? "Select an approved Market List."
          : creationType === "DIRECT" && !businessUnitId
            ? "Business Unit is required for a direct purchase order."
            : creationType === "DIRECT" && (!departmentId || !locationId)
              ? "Department and location are required for a direct purchase order."
              : !orderDate
                ? "Order date is required."
                : !expectedDate
                  ? "Estimated Delivery Date is required."
                  : creationType !== "FROM_ML" &&
                      expectedDate &&
                      isBeforeDate(expectedDate, orderDate)
                    ? "Estimated Delivery Date cannot be before Order Date."
                    : !items.length
                      ? "Add at least one item."
                      : items.some(
                            (item) => item.quantity <= 0 || item.unit_price < 0,
                          )
                        ? "Quantities must be positive and unit costs cannot be negative."
                        : "";
    if (validation) {
      setFormError(validation);
      const field = !supplierId
        ? "supplier"
        : (creationType === "FROM_PR" && !selectedPRs.length) ||
            (creationType === "FROM_ML" && !selectedML)
          ? "source"
          : creationType === "DIRECT" && !businessUnitId
            ? "businessUnit"
            : creationType === "DIRECT" && !departmentId
              ? "department"
              : creationType === "DIRECT" && !locationId
                ? "location"
                : !orderDate
                  ? "orderDate"
                  : !expectedDate ||
                      (creationType !== "FROM_ML" &&
                        isBeforeDate(expectedDate, orderDate))
                    ? "expectedDate"
                    : "items";
      focusFormField(field);
      return;
    }
    setFormError("");
    const payload = {
      creation_type: creationType,
      market_list_id: creationType === "FROM_ML" ? selectedML?.id : undefined,
      market_list_items:
        creationType === "FROM_ML"
          ? items.map((item) => ({
              market_list_item_id: item.market_list_item_id!,
              quantity: item.quantity,
            }))
          : undefined,
      supplier_id: supplierId,
      business_unit_id: businessUnitId,
      department_id: departmentId,
      location_id: locationId,
      order_date: orderDate,
      expected_date: expectedDate,
      notes,
      purchase_requisition_ids:
        creationType === "FROM_PR"
          ? (initialData?.purchase_requisition_ids ??
            selectedPRs.map((item) => item.id))
          : [],
      items: items.map(
        ({
          product_code: _a,
          product_name: _b,
          requested_quantity: _c,
          remaining_quantity: _d,
          source_pr_number: _e,
          source_ml_number: _f,
          market_list_item_id: _g,
          ...item
        }) => item,
      ),
    };
    setSubmitting(true);
    try {
      const result = await onSubmit(payload);
      if (result !== false) recovery.clear();
      else
        setFormError(
          "Purchase Order could not be saved. Your input is still available here.",
        );
    } catch {
      setFormError(
        "Purchase Order could not be saved. Your input is still available here.",
      );
    } finally {
      setSubmitting(false);
    }
  };
  const discard = () => {
    if (
      !window.confirm(
        "Discard the unfinished Purchase Order input stored in this browser?",
      )
    )
      return;
    recovery.clear();
    onClose();
  };
  const orderMin = undefined;
  const expectedMin = orderDate || undefined;
  return (
    <FormDialog
      open={open}
      title={editing ? "Edit Purchase Order" : "Create Purchase Order"}
      description={
        editing
          ? initialData?.po_number
          : "Create an order from a requisition, market list, or directly."
      }
      size="large"
      busy={busy}
      onRequestClose={requestClose}
      footer={
        <FormFooter
          onCancel={requestClose}
          onSubmit={save}
          submitLabel={editing ? "Save Changes" : "Create Purchase Order"}
          saving={busy}
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
                  className="text-xs font-medium text-slate-600 underline hover:text-red-700"
                  onClick={discard}
                  disabled={busy}
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
          Preparing purchase order…
        </p>
      ) : (
        <div className="space-y-5">
          <FormErrorSummary message={formError} />
          {!editing && (
            <fieldset
              className="rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2"
              aria-label="Choose Creation Type"
            >
              <legend className="sr-only">Choose Creation Type</legend>
              <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs sm:text-sm">
                <label className="flex items-center gap-2 whitespace-nowrap">
                  <input
                    type="radio"
                    checked={creationType === "FROM_PR"}
                    onChange={() => changeType("FROM_PR")}
                  />{" "}
                  From Purchase Requisition
                </label>
                <label className="flex items-center gap-2 whitespace-nowrap">
                  <input
                    type="radio"
                    checked={creationType === "FROM_ML"}
                    onChange={() => changeType("FROM_ML")}
                  />{" "}
                  From Market List
                </label>
                <label className="flex items-center gap-2 whitespace-nowrap">
                  <input
                    type="radio"
                    checked={creationType === "DIRECT"}
                    onChange={() => changeType("DIRECT")}
                  />{" "}
                  Direct Purchase Order
                </label>
              </div>
            </fieldset>
          )}
          {editing && (
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              PO number <strong>{initialData.po_number}</strong> and its
              creation source are locked.
            </div>
          )}
          <FormSection title="Order Information">
            <PurchaseOrderHeader
              fromRequisition={creationType === "FROM_PR"}
              fromMarketList={creationType === "FROM_ML"}
              sourceLocked={editing && creationType === "FROM_PR"}
              suppliers={suppliers}
              approvedPRs={availablePRs}
              approvedMLs={approvedMLs}
              selectedML={selectedML}
              businessUnits={businessUnits.data ?? []}
              departments={departments.data ?? []}
              locations={locations.data ?? []}
              supplierId={supplierId}
              selectedPRs={selectedPRs}
              businessUnitId={businessUnitId}
              departmentId={departmentId}
              locationId={locationId}
              orderDate={orderDate}
              expectedDate={expectedDate}
              notes={notes}
              orderDateMin={orderMin}
              expectedDateMin={expectedMin}
              onSupplierChange={setSupplierId}
              onSelectPRs={selectPRs}
              onSelectML={selectML}
              onBusinessUnitChange={changeBusinessUnit}
              onDepartmentChange={setDepartmentId}
              onLocationChange={setLocationId}
              onOrderDateChange={setOrderDate}
              onExpectedDateChange={setExpectedDate}
              onNotesChange={setNotes}
            />
          </FormSection>
          <FormSection
            title="Order Items"
            description="Select items, quantities, and purchase prices."
          >
            <PurchaseOrderItems
              items={items}
              products={products}
              supplierProducts={supplierProducts}
              supplierId={supplierId}
              sourceType={creationType}
              editing={editing}
              onChange={setItems}
            />
          </FormSection>
          <PurchaseOrderSummary total={total} />
        </div>
      )}
    </FormDialog>
  );
}

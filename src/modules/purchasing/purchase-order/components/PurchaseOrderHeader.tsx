import { useEffect, useState } from "react";
import Input from "@/components/ui/Input";
import SearchableSelect from "@/components/form/SearchableSelect";
import FormField from "@/components/form-system/FormField";
import FormGrid from "@/components/form-system/FormGrid";
import PurchaseRequisitionPicker from "./PurchaseRequisitionPicker";
import MarketListPicker, { type MarketListOption } from "./MarketListPicker";

interface Option {
  id: number;
  code?: string;
  name: string;
}
interface Props {
  fromRequisition: boolean;
  fromMarketList?: boolean;
  sourceLocked?: boolean;
  suppliers: Option[];
  approvedPRs: any[];
  approvedMLs?: MarketListOption[];
  selectedML?: MarketListOption;
  businessUnits: Option[];
  departments: Option[];
  locations: Option[];
  supplierId?: number;
  selectedPRs: any[];
  businessUnitId?: number;
  departmentId?: number;
  locationId?: number;
  orderDate: string;
  expectedDate: string;
  notes: string;
  orderDateMin?: string;
  expectedDateMin?: string;
  onSupplierChange: (id: number) => void;
  onSelectPRs: (items: any[]) => void;
  onSelectML: (item?: MarketListOption) => void;
  onBusinessUnitChange: (id: number | undefined) => void;
  onDepartmentChange: (id: number | undefined) => void;
  onLocationChange: (id: number | undefined) => void;
  onOrderDateChange: (value: string) => void;
  onExpectedDateChange: (value: string) => void;
  onNotesChange: (value: string) => void;
}
const label = (item: Option) =>
  item.code ? `${item.code} - ${item.name}` : item.name;
export default function PurchaseOrderHeader(props: Props) {
  const source = props.selectedPRs[0];
  const ml = props.selectedML;
  const [notesOpen, setNotesOpen] = useState(Boolean(props.notes.trim()));
  useEffect(() => {
    if (props.notes.trim()) setNotesOpen(true);
  }, [props.notes]);
  return (
    <FormGrid>
      {props.fromRequisition && (
        <div data-form-field="source" className="md:col-span-2">
          <PurchaseRequisitionPicker
            options={props.approvedPRs}
            selected={props.selectedPRs}
            disabled={props.sourceLocked}
            onChange={props.onSelectPRs}
          />
        </div>
      )}
      {props.fromMarketList && (
        <div data-form-field="source" className="md:col-span-2">
          <MarketListPicker
            options={props.approvedMLs ?? []}
            selected={ml}
            disabled={props.sourceLocked}
            onChange={props.onSelectML}
          />
        </div>
      )}
      <div data-form-field="supplier">
        <SearchableSelect
          label="Supplier"
          value={props.supplierId}
          required
          placeholder="Type supplier code or name..."
          options={props.suppliers.map((supplier) => ({
            id: supplier.id,
            label: label(supplier),
            keywords: [supplier.code ?? "", supplier.name],
          }))}
          onChange={(id) => props.onSupplierChange(id ?? 0)}
        />
      </div>
      {!props.fromRequisition && !props.fromMarketList && (
        <>
          <div data-form-field="businessUnit">
            <SearchableSelect
              label="Business Unit"
              value={props.businessUnitId}
              required
              placeholder="Type business unit..."
              options={props.businessUnits.map((item) => ({
                id: item.id,
                label: label(item),
                keywords: [item.code ?? "", item.name],
              }))}
              onChange={props.onBusinessUnitChange}
            />
          </div>
          <div data-form-field="department">
            <SearchableSelect
              label="Department"
              value={props.departmentId}
              required
              placeholder="Type department..."
              options={props.departments.map((item) => ({
                id: item.id,
                label: label(item),
                keywords: [item.code ?? "", item.name],
              }))}
              onChange={props.onDepartmentChange}
            />
          </div>
          <div data-form-field="location">
            <SearchableSelect
              label="Location"
              value={props.locationId}
              required
              placeholder="Type location..."
              options={props.locations.map((item) => ({
                id: item.id,
                label: label(item),
                keywords: [item.code ?? "", item.name],
              }))}
              onChange={props.onLocationChange}
            />
          </div>
        </>
      )}
      {props.fromRequisition && source && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm md:col-span-2">
          <div className="font-medium">
            Organization inherited from {props.selectedPRs.length} selected PR
            {props.selectedPRs.length > 1 ? "s" : ""}
          </div>
          <div className="mt-1 text-slate-600">
            Business Unit: {source.business_unit_name ?? "—"} · Department:{" "}
            {source.department_name ?? "—"} · Location:{" "}
            {source.location_name ?? "—"}
          </div>
        </div>
      )}
      {props.fromMarketList && ml && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm md:col-span-2">
          <div className="font-medium">
            Organization inherited from {ml.ml_number}
          </div>
          <div className="mt-1 text-slate-600">
            Business Unit: {ml.business_unit_name ?? "—"} · Department:{" "}
            {ml.department_name ?? "—"} · Location: {ml.location_name ?? "—"}
          </div>
        </div>
      )}
      <div data-form-field="orderDate">
        <FormField label="Order Date" required htmlFor="po-order-date">
          <Input
            id="po-order-date"
            type="date"
            data-accounting-date="true"
            min={props.orderDateMin}
            value={props.orderDate}
            onChange={(event) => props.onOrderDateChange(event.target.value)}
          />
        </FormField>
      </div>
      <div data-form-field="expectedDate">
        <FormField
          label="Estimated Delivery Date"
          required
          htmlFor="po-delivery-date"
        >
          <Input
            id="po-delivery-date"
            type="date"
            min={props.expectedDateMin}
            value={props.expectedDate}
            onChange={(event) => props.onExpectedDateChange(event.target.value)}
          />
        </FormField>
      </div>
      <div className="md:col-span-2">
        <button
          type="button"
          className="flex items-center gap-2 text-xs font-medium text-emerald-700 hover:underline"
          onClick={() => setNotesOpen((current) => !current)}
          aria-expanded={notesOpen}
          aria-controls="po-notes-field"
        >
          {notesOpen ? "Hide notes" : "Add notes (optional)"}
          {!notesOpen && props.notes.trim() && (
            <span className="rounded bg-slate-100 px-1.5 text-slate-600">
              Saved
            </span>
          )}
        </button>
        {notesOpen && (
          <div id="po-notes-field" className="mt-2">
            <FormField label="Notes" htmlFor="po-notes">
              <textarea
                id="po-notes"
                rows={2}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={props.notes}
                onChange={(event) => props.onNotesChange(event.target.value)}
              />
            </FormField>
          </div>
        )}
      </div>
    </FormGrid>
  );
}

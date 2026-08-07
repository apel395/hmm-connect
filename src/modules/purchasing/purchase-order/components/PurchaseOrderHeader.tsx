import Input from "@/components/ui/Input";
import type { ReactNode } from "react";

interface Option { id:number; code?:string; name:string }
interface Props {
  fromRequisition:boolean; sourceLocked?:boolean; suppliers:Option[]; approvedPRs:any[]; businessUnits:Option[]; departments:Option[]; locations:Option[];
  supplierId?:number; selectedPR?:any; businessUnitId?:number; departmentId?:number; locationId?:number;
  orderDate:string; expectedDate:string; notes:string;
  onSupplierChange:(id:number)=>void; onSelectPR:(id:number)=>void; onBusinessUnitChange:(id:number|undefined)=>void;
  onDepartmentChange:(id:number|undefined)=>void; onLocationChange:(id:number|undefined)=>void;
  onOrderDateChange:(value:string)=>void; onExpectedDateChange:(value:string)=>void; onNotesChange:(value:string)=>void;
}
const Select=({label,value,onChange,children,disabled=false}:{label:string;value:number|string|undefined;onChange:(value:number)=>void;children:ReactNode;disabled?:boolean})=><label className="text-sm font-medium">{label}<select disabled={disabled} className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 disabled:bg-slate-100" value={value??""} onChange={(event)=>onChange(Number(event.target.value))}>{children}</select></label>;
export default function PurchaseOrderHeader(props:Props){return <div className="grid gap-5 md:grid-cols-2">
  {props.fromRequisition&&<Select label="Approved Purchase Requisition" value={props.selectedPR?.id} onChange={props.onSelectPR} disabled={props.sourceLocked}><option value="">Select one approved PR</option>{props.approvedPRs.map((pr)=><option key={pr.id} value={pr.id}>{pr.pr_number}</option>)}</Select>}
  <Select label="Supplier" value={props.supplierId} onChange={props.onSupplierChange}><option value="">Select supplier</option>{props.suppliers.map((supplier)=><option key={supplier.id} value={supplier.id}>{supplier.code?`${supplier.code} - `:""}{supplier.name}</option>)}</Select>
  {!props.fromRequisition&&<><Select label="Business Unit" value={props.businessUnitId} onChange={(id)=>props.onBusinessUnitChange(id||undefined)}><option value="">Select business unit</option>{props.businessUnits.map((item)=><option key={item.id} value={item.id}>{item.code?`${item.code} - `:""}{item.name}</option>)}</Select><Select label="Department" value={props.departmentId} onChange={(id)=>props.onDepartmentChange(id||undefined)}><option value="">Select department</option>{props.departments.map((item)=><option key={item.id} value={item.id}>{item.code?`${item.code} - `:""}{item.name}</option>)}</Select><Select label="Location" value={props.locationId} onChange={(id)=>props.onLocationChange(id||undefined)}><option value="">Select location</option>{props.locations.map((item)=><option key={item.id} value={item.id}>{item.code?`${item.code} - `:""}{item.name}</option>)}</Select></>}
  {props.fromRequisition&&props.selectedPR&&<div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm md:col-span-2"><div className="font-medium">Organization inherited from {props.selectedPR.pr_number}</div><div className="mt-1 text-slate-600">Business Unit: {props.selectedPR.business_unit_name??"—"} · Department: {props.selectedPR.department_name??"—"} · Location: {props.selectedPR.location_name??"—"}</div></div>}
  <label className="text-sm font-medium">Order Date<Input className="mt-1" type="date" value={props.orderDate} onChange={(event)=>props.onOrderDateChange(event.target.value)}/></label><label className="text-sm font-medium">Estimated Delivery Date<Input className="mt-1" type="date" value={props.expectedDate} onChange={(event)=>props.onExpectedDateChange(event.target.value)}/></label><label className="text-sm font-medium md:col-span-2">Notes<textarea className="mt-1 min-h-24 w-full rounded-md border border-slate-300 p-3" value={props.notes} onChange={(event)=>props.onNotesChange(event.target.value)}/></label>
</div>}

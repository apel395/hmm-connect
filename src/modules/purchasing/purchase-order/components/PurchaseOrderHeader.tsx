import Input from "@/components/ui/Input";
import SearchableSelect from "@/components/form/SearchableSelect";
import PurchaseRequisitionPicker from "./PurchaseRequisitionPicker";
import MarketListPicker,{type MarketListOption} from "./MarketListPicker";

interface Option {id:number;code?:string;name:string}
interface Props {
 fromRequisition:boolean;fromMarketList?:boolean;sourceLocked?:boolean;suppliers:Option[];approvedPRs:any[];approvedMLs?:MarketListOption[];selectedML?:MarketListOption;
 businessUnits:Option[];departments:Option[];locations:Option[];supplierId?:number;selectedPRs:any[];businessUnitId?:number;departmentId?:number;locationId?:number;
 orderDate:string;expectedDate:string;notes:string;orderDateMin?:string;expectedDateMin?:string;
 onSupplierChange:(id:number)=>void;onSelectPRs:(items:any[])=>void;onSelectML:(item?:MarketListOption)=>void;onBusinessUnitChange:(id:number|undefined)=>void;onDepartmentChange:(id:number|undefined)=>void;onLocationChange:(id:number|undefined)=>void;onOrderDateChange:(value:string)=>void;onExpectedDateChange:(value:string)=>void;onNotesChange:(value:string)=>void;
}
const label=(item:Option)=>item.code?`${item.code} - ${item.name}`:item.name;
export default function PurchaseOrderHeader(props:Props){const source=props.selectedPRs[0];const ml=props.selectedML;return <div className="grid gap-5 md:grid-cols-2">
 {props.fromRequisition&&<PurchaseRequisitionPicker options={props.approvedPRs} selected={props.selectedPRs} disabled={props.sourceLocked} onChange={props.onSelectPRs}/>} 
 {props.fromMarketList&&<MarketListPicker options={props.approvedMLs??[]} selected={ml} disabled={props.sourceLocked} onChange={props.onSelectML}/>} 
 <SearchableSelect label="Supplier" value={props.supplierId} required placeholder="Type supplier code or name..." options={props.suppliers.map(supplier=>({id:supplier.id,label:label(supplier),keywords:[supplier.code??"",supplier.name]}))} onChange={id=>props.onSupplierChange(id??0)}/>
 {!props.fromRequisition&&!props.fromMarketList&&<><SearchableSelect label="Business Unit" value={props.businessUnitId} placeholder="Type business unit..." options={props.businessUnits.map(item=>({id:item.id,label:label(item),keywords:[item.code??"",item.name]}))} onChange={props.onBusinessUnitChange}/><SearchableSelect label="Department" value={props.departmentId} placeholder="Type department..." options={props.departments.map(item=>({id:item.id,label:label(item),keywords:[item.code??"",item.name]}))} onChange={props.onDepartmentChange}/><SearchableSelect label="Location" value={props.locationId} placeholder="Type location..." options={props.locations.map(item=>({id:item.id,label:label(item),keywords:[item.code??"",item.name]}))} onChange={props.onLocationChange}/></>}
 {props.fromRequisition&&source&&<div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm md:col-span-2"><div className="font-medium">Organization inherited from {props.selectedPRs.length} selected PR{props.selectedPRs.length>1?"s":""}</div><div className="mt-1 text-slate-600">Business Unit: {source.business_unit_name??"—"} · Department: {source.department_name??"—"} · Location: {source.location_name??"—"}</div></div>}
 {props.fromMarketList&&ml&&<div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm md:col-span-2"><div className="font-medium">Organization inherited from {ml.ml_number}</div><div className="mt-1 text-slate-600">Business Unit: {ml.business_unit_name??"—"} · Department: {ml.department_name??"—"} · Location: {ml.location_name??"—"}</div></div>}
 <label className="text-sm font-medium">Order Date<Input className="mt-1" type="date" data-accounting-date="true" min={props.orderDateMin} value={props.orderDate} onChange={event=>props.onOrderDateChange(event.target.value)}/></label><label className="text-sm font-medium">Estimated Delivery Date<Input className="mt-1" type="date" min={props.expectedDateMin} value={props.expectedDate} onChange={event=>props.onExpectedDateChange(event.target.value)}/></label><label className="text-sm font-medium md:col-span-2">Notes<textarea className="mt-1 min-h-24 w-full rounded-md border border-slate-300 p-3" value={props.notes} onChange={event=>props.onNotesChange(event.target.value)}/></label>
</div>}

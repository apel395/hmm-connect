import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import Button from "@/components/ui/Button";
import { listBusinessUnits } from "@/modules/admin/organization/api";

export default function ReportUnitButtons({value,onChange}:{value:string|number|undefined;onChange:(id:string)=>void}) {
  const units=useQuery({queryKey:["report-units"],queryFn:listBusinessUnits});
  useEffect(()=>{if(units.data?.length===1&&!value)onChange(String(units.data[0].id));},[units.data,value,onChange]);
  if(units.isError)return <p role="alert" className="text-sm text-red-700">Business units could not be loaded.</p>;
  return <div className="flex flex-wrap gap-1 print:hidden" aria-label="Report business unit">
    {units.data?.map(unit=><Button key={unit.id} size="sm" variant={String(value)===String(unit.id)?"primary":"outline"} onClick={()=>onChange(String(unit.id))}>{unit.name}</Button>)}
    {(!units.data||units.data.length>1)&&<Button size="sm" variant={!value?"primary":"outline"} disabled={units.isLoading} onClick={()=>onChange("")}>Consolidated</Button>}
  </div>;
}

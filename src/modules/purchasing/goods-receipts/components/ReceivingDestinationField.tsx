import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { destinationFor, destinationLabel, masterDestination, type LineRouting, type ReceivingDestination } from "../destination";

type Props = { name: string; line: LineRouting; onChange: (value: Partial<LineRouting>) => void };
export default function ReceivingDestinationField({ name, line, onChange }: Props) {
  const [expanded, setExpanded] = useState(false);
  const baseline = masterDestination(line.inventory_treatment);
  const effective = destinationFor(line);
  const exceptional = effective !== baseline;
  const canOverride = line.inventory_treatment === "STOCK" || line.inventory_treatment === "DIRECT_USE";
  return <div className="min-w-0 space-y-1">
    <div className="flex items-center justify-between gap-2">
      <span title={exceptional ? "Receiving exception" : "From Item Master"} className={`whitespace-nowrap text-xs ${exceptional ? "font-medium text-amber-800" : "text-slate-700"}`}>{destinationLabel(effective, line.inventory_treatment)}{exceptional ? " *" : ""}</span>
      {canOverride && <button type="button" className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-emerald-700" aria-label={`Destination options for ${name}`} title="Special case" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}><SlidersHorizontal size={14}/></button>}
    </div>
    {expanded && canOverride && <div className="space-y-1">
      <select aria-label={`Destination for ${name}`} className="h-8 w-full rounded border px-2 text-xs" value={line.destination_type ?? ""} onChange={event => onChange({ destination_type: (event.target.value || null) as ReceivingDestination | null, destination_override_reason: null })}>
        <option value="">Item Master ({destinationLabel(baseline)})</option>
        <option value="WAREHOUSE">Warehouse</option>
        <option value="DIRECT_USE">Direct Use</option>
      </select>
      {exceptional && <input aria-label={`Destination reason for ${name}`} className="h-8 w-full rounded border px-2 text-xs" maxLength={500} placeholder="Reason for special case" value={line.destination_override_reason ?? ""} onChange={event => onChange({destination_override_reason: event.target.value})}/>}
    </div>}
    {!expanded && line.destination_override_reason && <span className="block max-w-56 truncate text-[11px] text-slate-500" title={line.destination_override_reason}>{line.destination_override_reason}</span>}
  </div>;
}

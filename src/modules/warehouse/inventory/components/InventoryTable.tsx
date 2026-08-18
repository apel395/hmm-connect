import { Link } from "react-router-dom";
import Badge from "@/components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import type { Inventory } from "../types";

const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2});

export default function InventoryTable({ rows }: { rows: Inventory[] }) {
  return <div className="overflow-x-auto"><Table className="min-w-[1120px] text-xs">
    <THead><TR className="whitespace-nowrap"><TH className="px-4 py-2.5">Code</TH><TH className="px-4 py-2.5">Item</TH><TH className="px-4 py-2.5">Warehouse</TH><TH className="px-4 py-2.5 text-right">On Hand</TH><TH className="px-4 py-2.5">UOM</TH><TH className="px-4 py-2.5 text-right">Avg Cost</TH><TH className="px-4 py-2.5 text-right">Stock Value</TH><TH className="px-4 py-2.5">Health</TH><TH className="px-4 py-2.5">Trace</TH></TR></THead>
    <TBody>{rows.map(row=><TR key={row.id} className="whitespace-nowrap">
      <TD className="px-4 py-2.5 font-medium text-slate-600">{row.product_code}</TD>
      <TD className="max-w-[260px] px-4 py-2.5 font-medium text-slate-900"><span className="block truncate" title={row.product_name}>{row.product_name}</span></TD>
      <TD className="px-4 py-2.5"><span className="font-medium text-slate-800">{row.warehouse_name}</span><span className="ml-2 text-[11px] text-slate-400">{row.warehouse_code}</span></TD>
      <TD className="px-4 py-2.5 text-right font-semibold tabular-nums">{Number(row.quantity).toLocaleString("id-ID")}</TD>
      <TD className="px-4 py-2.5">{row.uom}</TD>
      <TD className="px-4 py-2.5 text-right tabular-nums">Rp {money(row.average_cost)}</TD>
      <TD className="px-4 py-2.5 text-right font-medium tabular-nums">Rp {money(row.stock_value)}</TD>
      <TD className="px-4 py-2.5">{row.below_minimum?<Badge variant="danger">Below Minimum</Badge>:row.needs_reorder?<Badge variant="warning">Reorder</Badge>:<Badge variant="success">Healthy</Badge>}</TD>
      <TD className="px-4 py-2.5"><Link className="font-medium text-emerald-700 hover:underline" to={`/inventory/movements?product_id=${row.product_id}&warehouse_id=${row.warehouse_id}`}>Movements</Link></TD>
    </TR>)}</TBody>
  </Table></div>;
}

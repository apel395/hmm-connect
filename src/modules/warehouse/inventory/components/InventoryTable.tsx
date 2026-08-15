import { Link } from "react-router-dom";
import Badge from "@/components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import type { Inventory } from "../types";

const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2});

export default function InventoryTable({ rows }: { rows: Inventory[] }) {
  return <div className="overflow-x-auto"><Table>
    <THead><TR><TH>Item</TH><TH>Warehouse</TH><TH className="text-right">On Hand</TH><TH>UOM</TH><TH className="text-right">Avg Cost</TH><TH className="text-right">Stock Value</TH><TH className="text-right">Min</TH><TH className="text-right">Reorder</TH><TH className="text-right">Max</TH><TH>Health</TH><TH>Trace</TH></TR></THead>
    <TBody>{rows.map(row=><TR key={row.id}>
      <TD><div className="font-medium">{row.product_name}</div><div className="text-xs text-slate-500">{row.product_code}</div></TD>
      <TD><div>{row.warehouse_name}</div><div className="text-xs text-slate-500">{row.warehouse_code}</div></TD>
      <TD className="text-right font-semibold tabular-nums">{Number(row.quantity).toLocaleString("id-ID")}</TD>
      <TD>{row.uom}</TD>
      <TD className="text-right tabular-nums">Rp {money(row.average_cost)}</TD>
      <TD className="text-right font-medium tabular-nums">Rp {money(row.stock_value)}</TD>
      <TD className="text-right tabular-nums">{Number(row.minimum_stock).toLocaleString("id-ID")}</TD>
      <TD className="text-right tabular-nums">{Number(row.reorder_level).toLocaleString("id-ID")}</TD>
      <TD className="text-right tabular-nums">{Number(row.maximum_stock).toLocaleString("id-ID")}</TD>
      <TD>{row.below_minimum?<Badge variant="danger">Below Minimum</Badge>:row.needs_reorder?<Badge variant="warning">Reorder</Badge>:<Badge variant="success">Healthy</Badge>}</TD>
      <TD><Link className="font-medium text-emerald-700 hover:underline" to={`/inventory/movements?product_id=${row.product_id}&warehouse_id=${row.warehouse_id}`}>Movements</Link></TD>
    </TR>)}</TBody>
  </Table></div>;
}

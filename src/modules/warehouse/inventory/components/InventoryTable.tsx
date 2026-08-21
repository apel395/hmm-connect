import { Link } from "react-router-dom";
import { Table, THead, TBody, TR, TH, TD, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import type { Inventory } from "../types";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function InventoryTable({ rows }: { rows: Inventory[] }) {
  return <Table className="min-w-[1000px]">
    <THead><TR className="whitespace-nowrap"><TH>Code</TH><TH>Item</TH><TH>Warehouse</TH><TH numeric>On Hand</TH><TH>UOM</TH><TH numeric>Avg Cost</TH><TH numeric>Stock Value</TH><TH>Trace</TH></TR></THead>
    <TBody>{rows.map(row => <TR key={row.id} className="whitespace-nowrap">
      <TD className="font-medium text-slate-600">{row.product_code}</TD>
      <TD className="max-w-[260px]"><span className="block truncate font-medium text-slate-900" title={row.product_name}>{row.product_name}</span></TD>
      <TD><TableCellStack primary={row.warehouse_name} secondary={row.warehouse_code}/></TD>
      <TD numeric className="font-semibold">{Number(row.quantity).toLocaleString("id-ID")}</TD>
      <TD>{row.uom}</TD>
      <TD numeric>Rp {money(row.average_cost)}</TD>
      <TD numeric className="font-medium">Rp {money(row.stock_value)}</TD>
      <TD><Link className={TABLE_UI.documentLink} to={`/inventory/movements?product_id=${row.product_id}&warehouse_id=${row.warehouse_id}`}>Movements</Link></TD>
    </TR>)}</TBody>
  </Table>;
}

import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import type { PurchaseOrder } from "../types";

interface Props { rows?: PurchaseOrder[]; onView: (row: PurchaseOrder) => void }

function badgeClass(status: string) {
  const styles: Record<string, string> = {
    DRAFT: "bg-slate-100 text-slate-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
    APPROVED: "bg-green-100 text-green-700", PARTIALLY_RECEIVED: "bg-blue-100 text-blue-700",
    RECEIVED: "bg-purple-100 text-purple-700", REJECTED: "bg-red-100 text-red-700",
  };
  return styles[status] ?? styles.DRAFT;
}

export default function PurchaseOrderTable({ rows = [], onView }: Props) {
  return <Table className="min-w-[1100px]">
    <THead><TR className="whitespace-nowrap"><TH>Purchase Order</TH><TH>Supplier</TH><TH>Organization</TH><TH>Dates</TH><TH numeric>Total</TH><TH>Approval</TH><TH>Receiving</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead>
    <TBody>{rows.map((row) => <TR key={row.id} className="whitespace-nowrap">
      <TD><TableCellStack primary={row.po_number} secondary={row.creation_type === "FROM_PR" ? `From ${row.source_pr_number ?? "PR"}` : "Direct"}/></TD>
      <TD className="font-medium">{row.supplier_name ?? "—"}</TD>
      <TD>{row.department_name || row.location_name ? <TableCellStack primary={row.department_name || row.location_name} secondary={row.department_name ? row.location_name : undefined}/> : "—"}</TD>
      <TD><TableCellStack primary={row.order_date} secondary={row.expected_date ? `Expected ${row.expected_date}` : undefined}/></TD>
      <TD numeric className="font-semibold">{Number(row.total_amount).toLocaleString("id-ID", { minimumFractionDigits: 2 })}</TD>
      <TD>{row.current_approver_role ?? row.approval_status ?? "—"}</TD>
      <TD>{row.status === "RECEIVED" ? "Fully Received" : row.status === "PARTIALLY_RECEIVED" ? "Partially Received" : "Not Received"}</TD>
      <TD><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${badgeClass(row.status)}`}>{row.status.replaceAll("_", " ")}</span></TD>
      <TD><div className="flex justify-end"><Button size="sm" variant="outline" onClick={() => onView(row)}>View</Button></div></TD>
    </TR>)}{rows.length === 0 && <TR><TD colSpan={9} className="p-8 text-center text-slate-500">No Purchase Orders Found</TD></TR>}</TBody>
  </Table>;
}

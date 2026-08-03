import Button from "@/components/ui/Button";
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
  return <div className="overflow-x-auto"><table className="min-w-[1500px] w-full border-collapse"><thead><tr className="border-b bg-slate-50">
    <th className="p-3 text-left">PO Number</th><th className="p-3 text-left">Creation Type</th><th className="p-3 text-left">Source PR</th><th className="p-3 text-left">Supplier</th><th className="p-3 text-left">Department</th><th className="p-3 text-left">Location</th><th className="p-3 text-left">Order Date</th><th className="p-3 text-left">Estimated Delivery Date</th><th className="p-3 text-right">Total</th><th className="p-3 text-center">Approval Level</th><th className="p-3 text-center">Receiving Status</th><th className="p-3 text-center">Status</th><th className="p-3 text-right">Actions</th>
  </tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-b hover:bg-slate-50">
    <td className="p-3 font-medium">{row.po_number}</td><td className="p-3">{row.creation_type === "FROM_PR" ? "From PR" : "Direct"}</td><td className="p-3">{row.source_pr_number ?? "—"}</td><td className="p-3">{row.supplier_name ?? "—"}</td><td className="p-3">{row.department_name ?? "—"}</td><td className="p-3">{row.location_name ?? "—"}</td><td className="p-3">{row.order_date}</td><td className="p-3">{row.expected_date ?? "—"}</td><td className="p-3 text-right">{Number(row.total_amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td className="p-3 text-center">{row.current_approver_role ?? row.approval_status ?? "—"}</td><td className="p-3 text-center">{row.status === "RECEIVED" ? "Fully Received" : row.status === "PARTIALLY_RECEIVED" ? "Partially Received" : "Not Received"}</td>
    <td className="p-3 text-center"><span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeClass(row.status)}`}>{row.status.replaceAll("_", " ")}</span></td>
    <td className="p-3 text-right"><Button size="sm" variant="outline" onClick={() => onView(row)}>View</Button></td>
  </tr>)}{rows.length === 0 && <tr><td colSpan={13} className="p-8 text-center text-slate-500">No Purchase Orders Found</td></tr>}</tbody></table></div>;
}

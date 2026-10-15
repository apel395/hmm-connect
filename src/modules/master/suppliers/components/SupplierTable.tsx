import { Eye, Pencil } from "lucide-react";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import type { Supplier } from "../types";

interface Props {
  rows: Supplier[];
  busyId?: number | null;
  onView: (supplier: Supplier) => void;
  onEdit: (supplier: Supplier) => void;
  onToggle: (supplier: Supplier) => void;
  onDelete?: (supplier: Supplier) => void;
}

export default function SupplierTable({ rows, busyId, onView, onEdit, onToggle }: Props) {
  return (
    <>
      <div className="workspace-table-stack">
        <Table className="workspace-item-table min-w-[1050px]">
          <THead><TR><TH>Code</TH><TH>Supplier</TH><TH>Contact</TH><TH>Bank Account</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={6} className="py-12 text-center text-slate-500">No suppliers match your search and status filter.</TD></TR>
            ) : rows.map((supplier) => {
              const contact = supplier.rows?.[0];
              return (
                <TR key={supplier.id}>
                  <TD className="font-semibold text-emerald-800">{supplier.code}</TD><TD><button type="button" className="font-medium text-emerald-800 hover:underline" onClick={() => onView(supplier)}>{supplier.name}</button></TD>
                  <TD><TableCellStack primary={contact?.pic_name || "—"} secondary={contact?.phone || undefined}/></TD>
                  <TD>{supplier.bank_name || supplier.bank_account_number ? <TableCellStack primary={supplier.bank_name || "Bank"} secondary={supplier.bank_account_number || undefined}/> : "—"}</TD>
                  <TD><Badge variant={supplier.is_active ? "success" : "secondary"}>{supplier.is_active ? "Active" : "Inactive"}</Badge></TD>
                  <TD><div className="flex min-w-max justify-end gap-2">
                    <Button size="xs" variant="ghost" title="Supplier details" aria-label={`View ${supplier.code}`} onClick={() => onView(supplier)}><Eye size={15}/></Button>
                    <Button size="xs" variant="outline" title="Edit supplier" aria-label={`Edit ${supplier.code}`} onClick={() => onEdit(supplier)}><Pencil size={15}/></Button>
                    <Button size="xs" variant={supplier.is_active ? "warning" : "success"} loading={busyId === supplier.id} onClick={() => onToggle(supplier)}>{supplier.is_active ? "Deactivate" : "Activate"}</Button>
                  </div></TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>
    </>
  );
}

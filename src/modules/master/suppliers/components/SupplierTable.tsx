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
      <div className="overflow-x-auto">
        <Table>
          <THead><TR><TH>Supplier</TH><TH>Contact</TH><TH>Bank Account</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={5} className="py-12 text-center text-slate-500">No suppliers match your search and status filter.</TD></TR>
            ) : rows.map((supplier) => {
              const contact = supplier.rows?.[0];
              return (
                <TR key={supplier.id}>
                  <TD><TableCellStack primary={supplier.name} secondary={supplier.code}/></TD>
                  <TD><TableCellStack primary={contact?.pic_name || "—"} secondary={contact?.phone || undefined}/></TD>
                  <TD>{supplier.bank_name || supplier.bank_account_number ? <TableCellStack primary={supplier.bank_name || "Bank"} secondary={supplier.bank_account_number || undefined}/> : "—"}</TD>
                  <TD><Badge variant={supplier.is_active ? "success" : "secondary"}>{supplier.is_active ? "Active" : "Inactive"}</Badge></TD>
                  <TD><div className="flex min-w-max justify-end gap-2">
                    <Button size="xs" variant="ghost" onClick={() => onView(supplier)}>View</Button>
                    <Button size="xs" variant="outline" onClick={() => onEdit(supplier)}>Edit</Button>
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

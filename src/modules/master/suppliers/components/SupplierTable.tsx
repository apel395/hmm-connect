import { useEffect, useState } from "react";
import Pagination from "@/components/datatable/Pagination";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
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

const PAGE_SIZE = 25;

export default function SupplierTable({ rows, busyId, onView, onEdit, onToggle }: Props) {
  const [page, setPage] = useState(1);
  const pages = Math.max(Math.ceil(rows.length / PAGE_SIZE), 1);
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => { setPage(1); }, [rows]);

  return (
    <>
      <div className="overflow-x-auto">
        <Table>
          <THead><TR><TH>Supplier Code</TH><TH>Supplier Name</TH><TH>Contact Person</TH><TH>Phone</TH><TH>Bank</TH><TH>Account Number</TH><TH>Status</TH><TH className="text-right">Actions</TH></TR></THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={8} className="py-12 text-center text-slate-500">No suppliers match your search and status filter.</TD></TR>
            ) : visibleRows.map((supplier) => {
              const contact = supplier.rows?.[0];
              return (
                <TR key={supplier.id}>
                  <TD className="whitespace-nowrap font-medium">{supplier.code}</TD>
                  <TD>{supplier.name}</TD><TD>{contact?.pic_name || "—"}</TD>
                  <TD className="whitespace-nowrap">{contact?.phone || "—"}</TD>
                  <TD>{supplier.bank_name || "—"}</TD><TD>{supplier.bank_account_number || "—"}</TD>
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
      {rows.length > 0 && <Pagination page={page} pages={pages} total={rows.length} pageSize={PAGE_SIZE} noun="suppliers" onChange={setPage}/>} 
    </>
  );
}

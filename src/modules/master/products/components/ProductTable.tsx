import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import type { Product } from "../types";

interface Props {
  rows?: Product[];
  onEdit?: (product: Product) => void;
}

export default function ProductTable({ rows = [], onEdit }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <Table>
          <THead>
            <TR>
              <TH>Code</TH><TH>Product</TH><TH>Group</TH><TH>Sub Group</TH>
              <TH>Purchase UOM</TH><TH>Usage UOM</TH><TH className="text-right">Conversion</TH>
              <TH>Status</TH><TH className="text-right">Actions</TH>
            </TR>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={9} className="py-10 text-center">No Products</TD></TR>
            ) : rows.map((row) => (
              <TR key={row.id}>
                <TD>{row.code}</TD><TD>{row.name}</TD><TD>{row.group_name}</TD><TD>{row.subgroup_name}</TD>
                <TD>{row.uom}</TD><TD>{row.usage_uom}</TD>
                <TD className="text-right">{Number(row.conversion).toLocaleString()}</TD>
                <TD><Badge variant={row.is_active ? "success" : "secondary"}>{row.is_active ? "Active" : "Inactive"}</Badge></TD>
                <TD><div className="flex justify-end"><Button size="sm" variant="outline" onClick={() => onEdit?.(row)}>Edit</Button></div></TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </div>
  );
}

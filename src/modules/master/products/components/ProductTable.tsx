import { Table, THead, TBody, TR, TH, TD, TableCellStack } from "@/components/ui/Table";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import type { Product } from "../types";

interface Props {
  rows?: Product[];
  onEdit?: (product: Product) => void;
}

const taxLabel = (row: Product) => {
  if (row.tax_category === "REVIEW_REQUIRED") return "Review Required";
  if (!row.is_taxable) return row.tax_category === "EXEMPT" ? "Exempt" : "Non PPN";
  return `PPN ${Number(row.tax_rate || 0).toLocaleString()}%`;
};

export default function ProductTable({ rows = [], onEdit }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <Table>
          <THead>
            <TR>
              <TH>Product</TH><TH>Classification</TH><TH>UOM</TH><TH numeric>Minimum Stock</TH><TH>PPN</TH><TH>Status</TH><TH numeric>Actions</TH>
            </TR>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={7} className="py-10 text-center">No Products</TD></TR>
            ) : rows.map((row) => (
              <TR key={row.id}>
                <TD><TableCellStack primary={row.name} secondary={row.code}/></TD><TD><TableCellStack primary={row.group_name} secondary={row.subgroup_name}/></TD><TD><TableCellStack primary={row.uom} secondary={`${row.usage_uom} · ×${Number(row.conversion).toLocaleString("id-ID")}`}/></TD>
                <TD numeric>{Number(row.minimum_stock ?? 0).toLocaleString("id-ID")}</TD>
                <TD>
                  <div className="space-y-1">
                    <Badge variant={row.tax_category === "REVIEW_REQUIRED" ? "warning" : row.is_taxable ? "info" : "secondary"}>{taxLabel(row)}</Badge>
                    {row.tax_reason ? <div className="max-w-56 truncate text-xs text-slate-500" title={row.tax_reason}>{row.tax_reason}</div> : null}
                  </div>
                </TD>
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

import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
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
              <TH>Code</TH><TH>Product</TH><TH>Group</TH><TH>Sub Group</TH>
              <TH>Purchase UOM</TH><TH>Usage UOM</TH><TH className="text-right">Conversion</TH>
              <TH className="text-right">Minimum Stock</TH><TH>Market</TH><TH>PPN</TH><TH>Status</TH><TH className="text-right">Actions</TH>
            </TR>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={12} className="py-10 text-center">No Products</TD></TR>
            ) : rows.map((row) => (
              <TR key={row.id}>
                <TD>{row.code}</TD><TD>{row.name}</TD><TD>{row.group_name}</TD><TD>{row.subgroup_name}</TD>
                <TD>{row.uom}</TD><TD>{row.usage_uom}</TD>
                <TD className="text-right">{Number(row.conversion).toLocaleString()}</TD>
                <TD className="text-right tabular-nums">{Number(row.minimum_stock ?? 0).toLocaleString("id-ID")}</TD>
                <TD><Badge variant={row.is_market_item ? "success" : "secondary"}>{row.is_market_item ? "Market" : "No"}</Badge></TD>
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

import { Eye, Pencil } from "lucide-react";
import { Table, THead, TBody, TR, TH, TD, TableCellStack } from "@/components/ui/Table";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import type { AccountLookup } from "@/modules/master/chart-of-accounts/types";
import type { Product } from "../types";

interface Props {
  rows?: Product[];
  accounts?: AccountLookup[];
  onEdit?: (product: Product) => void;
  onView?: (product: Product) => void;
}

const taxLabel = (row: Product) => {
  if (row.item_type === "SELL") {
    const pbjt = Number(row.pbjt_rate || 0), ppn = Number(row.sales_ppn_rate || 0);
    return pbjt > 0 ? `PBJT ${pbjt}%` : ppn > 0 ? `PPN ${ppn}%` : "No sales tax";
  }
  if (row.tax_category === "REVIEW_REQUIRED") return "Tax Review";
  if (!row.is_taxable) return row.tax_category === "EXEMPT" ? "Exempt" : "Non PPN";
  return `PPN ${Number(row.tax_rate || 0).toLocaleString()}%`;
};

const treatmentLabel = (value: Product["inventory_treatment"]) => ({
  STOCK: "Stock",
  DIRECT_USE: "Direct Use",
  FIXED_ASSET: "Fixed Asset",
  NON_STOCK: "Non-stock",
  REVIEW_REQUIRED: "Review",
}[value] ?? value);

const treatmentVariant = (value: Product["inventory_treatment"]) =>
  value === "REVIEW_REQUIRED" ? "warning" : value === "STOCK" ? "success" : "secondary";

export default function ProductTable({ rows = [], accounts = [], onEdit, onView }: Props) {
  const byId = new Map(accounts.map((account) => [account.id, account]));

  const mappedAccount = (row: Product) => {
    const id =
      row.inventory_treatment === "STOCK" ? row.inventory_account_id :
      row.inventory_treatment === "FIXED_ASSET" ? row.asset_account_id :
      ["DIRECT_USE", "NON_STOCK"].includes(row.inventory_treatment) ? row.purchase_account_id :
      null;
    return id ? byId.get(id) : undefined;
  };

  const readiness = (row: Product) => {
    if (row.item_type === "SELL") return Number(row.pbjt_rate || 0) > 0 || Number(row.sales_ppn_rate || 0) > 0 || Number(row.pph23_rate || 0) > 0 ? "Tax posting pending" : "Catalogued";
    const taxReady = row.tax_category !== "REVIEW_REQUIRED";
    const accountingReady =
      row.inventory_treatment === "STOCK" ? Boolean(row.inventory_account_id) :
      row.inventory_treatment === "FIXED_ASSET" ? Boolean(row.asset_account_id) :
      ["DIRECT_USE", "NON_STOCK"].includes(row.inventory_treatment) ? Boolean(row.purchase_account_id) :
      false;
    if (!taxReady) return "Tax Review";
    if (!accountingReady) return row.inventory_treatment === "REVIEW_REQUIRED" ? "Treatment Review" : "Missing COA";
    return "Ready";
  };

  return (
    <div className="workspace-table-stack">
      <div className="workspace-table-stack">
        <Table className="workspace-item-table min-w-[1400px]">
          <THead>
            <TR>
              <TH className="w-[148px]">Item code</TH><TH>Item name</TH>
              <TH>Type / Price</TH>
              <TH>Classification</TH>
              <TH>Department</TH>
              <TH>Treatment</TH>
              <TH>UOM</TH>
              <TH>PPN</TH>
              <TH>Accounting COA</TH>
              <TH>Readiness</TH>
              <TH>Status</TH>
              <TH numeric>Actions</TH>
            </TR>
          </THead>
          <TBody>
            {rows.length === 0 ? (
              <TR><TD colSpan={12} className="py-10 text-center">No Products</TD></TR>
            ) : rows.map((row) => {
              const account = mappedAccount(row);
              const state = readiness(row);
              const subgroup = row.subgroup_name === "GRESORIS" ? "GROCERIES" : row.subgroup_name;
              return (
                <TR key={row.id}>
                  <TD className="font-semibold text-emerald-800"><span title={row.code}>{row.code}</span></TD><TD className="max-w-[320px]"><button type="button" className="block max-w-full truncate font-medium text-emerald-800 hover:underline" title={row.name} onClick={() => onView?.(row)}>{row.name}</button></TD>
                  <TD><TableCellStack primary={row.item_type === "SELL" ? "Sell" : "Buy"} secondary={row.item_type === "SELL" ? `Rp ${Number(row.selling_price ?? 0).toLocaleString("id-ID")}` : `Rp ${Number(row.reference_cost ?? row.cost_price ?? 0).toLocaleString("id-ID")} / ${row.uom}`}/></TD>
                  <TD><TableCellStack primary={row.group_name} secondary={row.item_type === "SELL" ? undefined : subgroup}/></TD>
                  <TD className="max-w-[150px] truncate" title={row.department_name || "Shared"}>{row.department_name || "Shared"}</TD>
                  <TD><Badge variant={treatmentVariant(row.inventory_treatment)}>{treatmentLabel(row.inventory_treatment)}</Badge></TD>
                  <TD><TableCellStack primary={row.uom} secondary={`${row.usage_uom} · ×${Number(row.conversion).toLocaleString("id-ID")}`}/></TD>
                  <TD>
                    <Badge variant={row.item_type === "SELL" ? "info" : row.tax_category === "REVIEW_REQUIRED" ? "warning" : row.is_taxable ? "info" : "secondary"}>
                      {taxLabel(row)}
                    </Badge>
                  </TD>
                  <TD>
                    {account
                      ? <TableCellStack primary={account.account_name} secondary={account.account_code}/>
                      : <span className="text-sm text-slate-400">—</span>}
                  </TD>
                  <TD>
                    <Badge variant={state === "Ready" ? "success" : state === "Catalogued" ? "secondary" : "warning"}>{state}</Badge>
                  </TD>
                  <TD><Badge variant={row.is_active ? "success" : "secondary"}>{row.is_active ? "Active" : "Inactive"}</Badge></TD>
                  <TD><div className="flex justify-end gap-2">
                    <Button size="xs" variant="ghost" title="Item details" aria-label={`View ${row.code}`} onClick={() => onView?.(row)}><Eye size={15}/></Button>
                    <Button size="xs" variant="ghost" title="Edit item" aria-label={`Edit ${row.code}`} onClick={() => onEdit?.(row)}><Pencil size={15}/></Button>
                  </div></TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>
    </div>
  );
}

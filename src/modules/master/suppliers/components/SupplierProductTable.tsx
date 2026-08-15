import { useEffect, useState } from "react";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import type { SupplierProduct } from "../typesSupplierProduct";

interface Props {
  rows?: SupplierProduct[];
  onDelete?: (row: SupplierProduct) => void;
}

const PAGE_SIZE = 20;

export default function SupplierProductTable({ rows = [], onDelete }: Props) {
  const [page, setPage] = useState(1);
  const pages = Math.max(Math.ceil(rows.length / PAGE_SIZE), 1);
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => { setPage(1); }, [rows]);

  return <>
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead><tr className="border-b"><th className="p-3 text-left">Product</th><th className="p-3 text-left">Purchase UOM</th><th className="p-3 text-right">Last Price</th><th className="p-3 text-right">Lead Time</th><th className="p-3 text-center">Preferred</th><th /></tr></thead>
        <tbody>
          {visibleRows.map((row) => <tr key={row.id} className="border-b"><td className="p-3">{row.product_name}</td><td className="p-3">{row.purchase_uom}</td><td className="p-3 text-right">{row.last_price.toLocaleString()}</td><td className="p-3 text-right">{row.lead_time} day(s)</td><td className="text-center">{row.preferred ? "✓" : ""}</td><td className="text-right"><Button size="sm" variant="danger" onClick={() => onDelete?.(row)}>Remove</Button></td></tr>)}
          {rows.length === 0 && <tr><td colSpan={6} className="p-8 text-center">No Products Assigned</td></tr>}
        </tbody>
      </table>
    </div>
    {rows.length > 0 && <Pagination page={page} pages={pages} total={rows.length} pageSize={PAGE_SIZE} noun="products" onChange={setPage}/>} 
  </>;
}

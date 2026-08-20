import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { stockOpnameApi } from "./api";

const PAGE_SIZE = 25;
const input =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function StockOpnamePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [show, setShow] = useState(false);
  const [warehouseId, setWarehouseId] = useState<number>();
  const [notes, setNotes] = useState("");
  const warehouses = useWarehouses();
  const query = useQuery({
    queryKey: ["stock-opnames", page, search, status],
    queryFn: async () =>
      (
        await stockOpnameApi.list({
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          status: status === "ALL" ? undefined : status,
        })
      ).data,
  });
  const create = useMutation({
    mutationFn: () => {
      if (!warehouseId) throw new Error("Warehouse is required");
      return stockOpnameApi.create({
        warehouse_id: warehouseId,
        notes: notes || undefined,
      });
    },
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: ["stock-opnames"] });
      setShow(false);
      navigate(`/stock-opnames/${r.data.id}`);
    },
  });
  const data = query.data;
  const rows = data?.items ?? [];
  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock Opname"
        description="Physical inventory count, variance approval, and controlled stock adjustment."
        actions={
          <Button onClick={() => setShow(true)}>Create Stock Opname</Button>
        }
      />
      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_220px]">
          <input
            className={input}
            placeholder="Search opname number"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          <select
            className={input}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            {[
              "ALL",
              "DRAFT",
              "PENDING_APPROVAL",
              "APPROVED",
              "POSTED",
              "REJECTED",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </div>
      </Card>
      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-xs">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left">Number</th>
                <th className="px-4 py-3 text-left">Count Date</th>
                <th className="px-4 py-3 text-left">Warehouse</th>
                <th className="px-4 py-3 text-left">Location</th>
                <th className="px-4 py-3 text-right">Items</th>
                <th className="px-4 py-3 text-right">Variance</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t whitespace-nowrap">
                  <td className="px-4 py-3 font-medium">
                    <Link
                      className="text-emerald-700 hover:underline"
                      to={`/stock-opnames/${row.id}`}
                    >
                      {row.opname_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{row.count_date}</td>
                  <td className="px-4 py-3">{row.warehouse_name ?? "—"}</td>
                  <td className="px-4 py-3">{row.location_name ?? "—"}</td>
                  <td className="px-4 py-3 text-right">{row.total_items}</td>
                  <td className="px-4 py-3 text-right">
                    {Number(row.total_variance_quantity || 0).toLocaleString(
                      "id-ID",
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {row.status.replaceAll("_", " ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4">
          <Pagination
            page={page}
            pages={Math.max(data?.total_pages ?? 0, 1)}
            total={data?.total_items ?? 0}
            pageSize={PAGE_SIZE}
            noun="stock opnames"
            onChange={setPage}
          />
        </div>
      </Card>
      {show && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6">
            <h2 className="text-lg font-semibold">Create Stock Opname</h2>
            <p className="mb-5 text-xs text-slate-500">
              Inventory quantities and average costs are snapshotted when this
              document is created.
            </p>
            <select
              className={input}
              value={warehouseId ?? ""}
              onChange={(e) =>
                setWarehouseId(Number(e.target.value) || undefined)
              }
            >
              <option value="">Warehouse</option>
              {(warehouses.data ?? [])
                .filter((w) => w.is_active)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} - {w.name}
                  </option>
                ))}
            </select>
            <textarea
              className="mt-3 min-h-20 w-full rounded-md border p-3 text-sm"
              placeholder="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            {create.error && (
              <p className="mt-2 text-sm text-red-600">
                {create.error instanceof Error
                  ? create.error.message
                  : "Unable to create"}
              </p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShow(false)}>
                Cancel
              </Button>
              <Button
                disabled={create.isPending}
                onClick={() => create.mutate()}
              >
                Create
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

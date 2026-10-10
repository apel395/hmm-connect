import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import useAuthorization from "@/hooks/useAuthorization";
import { useMutation,useQuery,useQueryClient } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useEffect,useRef,useState } from "react";
import { useNavigate,useParams } from "react-router-dom";
import { stockOpnameApi } from "./api";

export default function StockOpnameDetailPage() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasPermission } = useAuthorization();
  const query = useQuery({
    queryKey: ["stock-opname", id],
    queryFn: async () => (await stockOpnameApi.detail(id)).data,
    enabled: Number.isFinite(id),
  });
  const [counts, setCounts] = useState<Record<number, string>>({});
  const [quickQuery, setQuickQuery] = useState("");
  const [quickOpen, setQuickOpen] = useState(false);
  const [quickItemId, setQuickItemId] = useState<number | null>(null);
  const [quickQty, setQuickQty] = useState("");
  const quickQtyRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (query.data)
      setCounts(
        Object.fromEntries(
          query.data.items.map((i) => [
            i.id,
            i.physical_quantity == null ? "" : String(i.physical_quantity),
          ]),
        ),
      );
  }, [query.data]);
  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["stock-opname", id] });
    await qc.invalidateQueries({ queryKey: ["stock-opnames"] });
  };
  const save = useMutation({
    mutationFn: () => {
      const items = query
        .data!.items.filter((i) => (counts[i.id] ?? "").trim() !== "")
        .map((i) => ({
          item_id: i.id,
          physical_quantity: Number(counts[i.id]),
        }));
      if (!items.length)
        throw new Error("Enter at least one physical count before saving");
      return stockOpnameApi.count(id, items);
    },
    onSuccess: refresh,
  });
  const saveItem = useMutation({
    mutationFn: (payload: { item_id: number; physical_quantity: number }) =>
      stockOpnameApi.count(id, [payload]),
    onSuccess: () => {
      setQuickItemId(null);
      setQuickQty("");
      setQuickQuery("");
      refresh();
    },
  });
  const setAllUncountedSystem = useMutation({
    mutationFn: () => {
      const pending = (query.data?.items ?? []).filter(
        (i) => (counts[i.id] ?? "").trim() === "",
      );
      if (!pending.length)
        throw new Error("All items are already counted");
      return stockOpnameApi.count(
        id,
        pending.map((i) => ({
          item_id: i.id,
          physical_quantity: Number(i.system_quantity),
        })),
      );
    },
    onSuccess: refresh,
  });
  const submit = useMutation({
    mutationFn: () => stockOpnameApi.submit(id),
    onSuccess: refresh,
  });
  const post = useMutation({
    mutationFn: () => stockOpnameApi.post(id),
    onSuccess: refresh,
  });
  const unpost = useMutation({
    mutationFn: () => stockOpnameApi.unpost(id),
    onSuccess: refresh,
  });
  const voidIt = useMutation({
    mutationFn: (reason: string) => stockOpnameApi.void(id, reason),
    onSuccess: () => {
      refresh();
      navigate("/stock-opnames");
    },
  });
  const askVoid = () => {
    const reason = window.prompt(
      "Void this Stock Opname? This cancels the count and lets you create a new one. Reason (required):",
    )?.trim();
    if (reason == null) return;
    if (!reason) return window.alert("A void reason is required.");
    if (!window.confirm(`Void ${d?.opname_number}? This cannot be undone.`)) return;
    voidIt.mutate(reason);
  };
  const d = query.data;
  if (!d) return <div>Loading...</div>;
  const editable = d.status !== "POSTED";
  const canCount = editable && d.allowed_actions?.can_edit === true;

  const matches = quickQuery.trim()
    ? d.items
        .map((i) => ({ i, hay: `${i.product_code ?? ""} ${i.product_name ?? ""}`.toLowerCase() }))
        .filter((m) => m.hay.includes(quickQuery.trim().toLowerCase()))
        .slice(0, 50)
    : [];
  const counted = d.items.filter((i) => (counts[i.id] ?? "").trim() !== "").length;
  const varianceTotal = d.items.reduce((sum, i) => sum + Number(i.variance_value ?? 0), 0);
  const progressPct = d.items.length ? Math.round((counted / d.items.length) * 100) : 0;
  const canSaveQuick =
    quickItemId != null &&
    quickQty.trim() !== "" &&
    Number.isFinite(Number(quickQty)) &&
    Number(quickQty) >= 0;
  const selectItem = (item: any) => {
    setQuickItemId(item.id);
    setQuickQty((counts[item.id] ?? "").trim() === "" ? "" : String(counts[item.id] ?? ""));
    setQuickQuery(`${item.product_code ?? ""} — ${item.product_name ?? ""}`);
    setQuickOpen(false);
    requestAnimationFrame(() => quickQtyRef.current?.focus());
  };
  const saveQuick = () => {
    if (!canSaveQuick || quickItemId == null) return;
    saveItem.mutate({ item_id: quickItemId, physical_quantity: Number(quickQty) });
  };
  return (
    <div className="space-y-6">
      <PageHeader
        title={d.opname_number}
        description={`${d.warehouse_name ?? "Warehouse"} • ${d.count_date}`}
        actions={
          <div className="flex gap-2">
            {canCount && d.items.length > 0 && (
              <>
                <Button
                  variant="secondary"
                  disabled={save.isPending}
                  onClick={() => save.mutate()}
                >
                  Save Count
                </Button>
              </>
            )}
            {d.status === "DRAFT" && d.items.length > 0 && d.allowed_actions?.can_submit === true && (
              <Button
                disabled={submit.isPending}
                onClick={() => submit.mutate()}
              >
                Submit
              </Button>
            )}
            {d.status === "REJECTED" && d.items.length > 0 && d.allowed_actions?.can_submit === true && (
              <Button
                disabled={submit.isPending}
                onClick={() => submit.mutate()}
              >
                Resubmit
              </Button>
            )}
            {d.status === "APPROVED" && d.items.length > 0 && d.allowed_actions?.can_post === true && (
              <Button disabled={post.isPending} onClick={() => post.mutate()}>
                Post Adjustment
              </Button>
            )}
            {d.status === "POSTED" && d.allowed_actions?.can_unpost === true && (
              <Button
                variant="danger"
                disabled={unpost.isPending}
                onClick={() => {
                  if (window.confirm(`Unpost ${d.opname_number} and restore system quantities?`))
                    unpost.mutate();
                }}
              >
                Unpost
              </Button>
            )}
            {!["POSTED", "VOID"].includes(d.status) && hasPermission("stock_opname.manage") && (
              <Button
                variant="danger"
                disabled={voidIt.isPending}
                onClick={askVoid}
              >
                Void
              </Button>
            )}
            <WorkspaceBackButton />
            <Button variant="outline" onClick={() => navigate(`/stock-opnames/${id}/print`)}><Printer size={16}/> Print</Button>
</div>
        }
      />
      <Card className="p-4">
        <div className="grid gap-3 text-xs md:grid-cols-4">
          <div>
            <span className="text-slate-500">Status</span>
            <div className="font-semibold">{d.status.replaceAll("_", " ")}</div>
          </div>
          <div>
            <span className="text-slate-500">Warehouse</span>
            <div>{d.warehouse_name}</div>
          </div>
          <div>
            <span className="text-slate-500">Location</span>
            <div>{d.location_name ?? "—"}</div>
          </div>
          <div>
            <span className="text-slate-500">Department</span>
            <div>{d.department_name ?? "—"}</div>
          </div>
        </div>
      </Card>
      {canCount && d.items.length > 0 && (
        <Card className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="font-semibold">Quick Count Entry</div>
              <div className="text-xs text-slate-500">
                Scan or type an item code / name, enter the counted quantity, then press
                Enter to save that item immediately.
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={setAllUncountedSystem.isPending}
              onClick={() => setAllUncountedSystem.mutate()}
            >
              Set All Uncounted = System
            </Button>
          </div>
          <div className="mt-3">
            <div className="flex justify-between text-xs text-slate-500">
              <span>
                {counted} of {d.items.length} items counted
              </span>
              <span>Variance {varianceTotal.toLocaleString("id-ID")}</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_auto_auto]">
            <div className="relative">
              <input
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                placeholder="Scan or type item code / name..."
                autoComplete="off"
                autoFocus
                value={quickQuery}
                onChange={(event) => {
                  setQuickQuery(event.target.value);
                  setQuickOpen(true);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && matches.length) {
                    event.preventDefault();
                    selectItem(matches[0].i);
                  } else if (event.key === "Escape") {
                    setQuickOpen(false);
                    if (quickItemId != null) {
                      const item = d.items.find((i) => i.id === quickItemId);
                      if (item) setQuickQuery(`${item.product_code ?? ""} — ${item.product_name ?? ""}`);
                    }
                  }
                }}
              />
              {quickOpen && matches.length > 0 && (
                <>
                  <button
                    type="button"
                    aria-label="Close item options"
                    className="fixed inset-0 z-[9998] cursor-default"
                    onMouseDown={() => setQuickOpen(false)}
                  />
                  <div className="absolute left-0 top-full z-[9999] mt-1 max-h-80 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-xl">
                    {matches.map(({ i }) => (
                      <button
                        key={i.id}
                        type="button"
                        className="block w-full border-b border-slate-100 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-emerald-50"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => selectItem(i)}
                      >
                        <div className="font-medium text-slate-800">
                          {i.product_code} — {i.product_name}
                        </div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          System {Number(i.system_quantity).toLocaleString("id-ID")} {i.uom}
                          {i.physical_quantity != null ? ` • Counted ${Number(i.physical_quantity).toLocaleString("id-ID")}` : ""}
                        </div>
                      </button>
                    ))}
                    {quickQuery.trim() && matches.length === 50 && (
                      <div className="px-3 py-2 text-xs text-slate-500">
                        Showing first 50 matches. Keep typing to narrow down.
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            <input
              ref={quickQtyRef}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
              type="number"
              min="0"
              step="0.0001"
              placeholder="Counted qty"
              value={quickQty}
              onChange={(event) => setQuickQty(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  if (canSaveQuick) saveQuick();
                }
              }}
            />
            <Button
              variant="outline"
              disabled={quickItemId == null}
              onClick={() => {
                if (quickItemId == null) return;
                const item = d.items.find((i) => i.id === quickItemId);
                if (item) setQuickQty(String(item.system_quantity));
              }}
            >
              Count = System
            </Button>
            <Button loading={saveItem.isPending} disabled={!canSaveQuick} onClick={saveQuick}>
              Save This Item
            </Button>
          </div>
        </Card>
      )}
      {d.items.length === 0 && (
        <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          This Stock Opname has no inventory snapshot. It cannot be counted,
          submitted, approved, or posted. Create a new Stock Opname after the
          warehouse contains inventory.
        </Card>
      )}
      <Card className="hidden print:block p-6">
        <h2 className="mb-4 border-b border-black pb-2 text-sm font-bold uppercase tracking-wide">
          Approval Signatures
        </h2>
        <div className="grid grid-cols-3 gap-10 text-center">
          {(d.approval_history ?? []).map((step) => (
            <div key={String(step.level ?? step.name)}>
              <div className="flex h-14 items-end justify-center">
                {step.signature_image && (
                  <img src={step.signature_image} alt="" className="max-h-14 max-w-full object-contain" />
                )}
              </div>
              <div className="border-t border-black pt-1 font-semibold">
                {step.signature_label || step.name || `Level ${step.level}`}
              </div>
              <div className="mt-1 text-[11px]">{step.signature_name || step.approver_name || step.status}</div>
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-xs">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Description</th>
                <th className="px-4 py-3 text-left">UOM</th>
                <th className="px-4 py-3 text-right">System</th>
                <th className="px-4 py-3 text-right">Physical</th>
                <th className="px-4 py-3 text-right">Variance</th>
                <th className="px-4 py-3 text-right">Unit Cost</th>
                <th className="px-4 py-3 text-right">Variance Value</th>
              </tr>
            </thead>
            <tbody>
              {d.items.map((i) => {
                const physical =
                  (counts[i.id] ?? "").trim() === ""
                    ? null
                    : Number(counts[i.id]);
                const variance =
                  physical == null
                    ? null
                    : physical - Number(i.system_quantity);
                return (
                  <tr key={i.id} className="border-t whitespace-nowrap">
                    <td className="px-4 py-2">{i.product_code}</td>
                    <td className="px-4 py-2">{i.product_name}</td>
                    <td className="px-4 py-2">{i.uom}</td>
                    <td className="px-4 py-2 text-right">
                      {Number(i.system_quantity).toLocaleString("id-ID")}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {canCount ? (
                        <input
                          className="h-8 w-28 rounded border px-2 text-right"
                          type="number"
                          min="0"
                          step="0.0001"
                          value={counts[i.id] ?? ""}
                          onChange={(e) =>
                            setCounts((old) => ({
                              ...old,
                              [i.id]: e.target.value,
                            }))
                          }
                        />
                      ) : (
                        i.physical_quantity == null
                          ? "—"
                          : Number(i.physical_quantity).toLocaleString("id-ID")
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {variance == null
                        ? i.variance_quantity == null
                          ? "—"
                          : Number(i.variance_quantity).toLocaleString("id-ID")
                        : variance.toLocaleString("id-ID")}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {Number(i.unit_cost).toLocaleString("id-ID")}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {Number(i.variance_value ?? 0).toLocaleString("id-ID")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      {(save.error || saveItem.error || setAllUncountedSystem.error || submit.error || post.error || unpost.error || voidIt.error) && (
        <p className="text-sm text-red-600">
          {(save.error || saveItem.error || setAllUncountedSystem.error || submit.error || post.error || unpost.error || voidIt.error) instanceof Error
            ? (save.error || saveItem.error || setAllUncountedSystem.error || submit.error || post.error || unpost.error || voidIt.error)?.message
            : "Action failed. Refresh and verify the Stock Opname status."}
        </p>
      )}
    </div>
  );
}

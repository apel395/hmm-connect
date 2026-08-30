import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import Button from "@/components/ui/Button";
import Dialog, { DialogContent } from "@/components/ui/Dialog";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { useMarketList, useMarketLists, useConvertMarketList } from "@/modules/purchasing/market-list/useMarketLists";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated?: (purchaseOrder: any) => void;
}

interface SelectedLine {
  market_list_item_id: number;
  quantity: number;
}

export default function MarketListPurchaseOrderDialog({ open, onClose, onCreated }: Props) {
  const [marketListId, setMarketListId] = useState<number>();
  const [supplierId, setSupplierId] = useState<number>();
  const [selected, setSelected] = useState<SelectedLine[]>([]);
  const [error, setError] = useState("");

  const marketLists = useMarketLists({ scope: "active", status: "APPROVED", page: 1, page_size: 100 });
  const detail = useMarketList(marketListId ?? 0);
  const suppliers = useSuppliers("");
  const convert = useConvertMarketList();

  useEffect(() => {
    if (!open) return;
    setMarketListId(undefined);
    setSupplierId(undefined);
    setSelected([]);
    setError("");
  }, [open]);

  useEffect(() => {
    if (!detail.data?.items) return;
    setSelected(detail.data.items.map((item: any) => ({
      market_list_item_id: item.id,
      quantity: Number(item.quantity),
    })));
  }, [detail.data]);

  const selectedItems = useMemo(
    () => selected.filter((item) => item.quantity > 0),
    [selected],
  );

  const updateQuantity = (id: number, quantity: number) => {
    setSelected((current) => current.map((item) =>
      item.market_list_item_id === id ? { ...item, quantity: Math.max(0, quantity) } : item,
    ));
  };

  const submit = async () => {
    if (!marketListId) return setError("Select an approved Market List.");
    if (!supplierId) return setError("Select a supplier.");
    if (!selectedItems.length) return setError("Select at least one Market List source line.");
    if (selectedItems.some((item) => !Number.isFinite(item.quantity) || item.quantity <= 0)) {
      return setError("Selected quantities must be greater than zero.");
    }
    setError("");
    try {
      const response = await convert.mutateAsync({
        id: marketListId,
        supplier_id: supplierId,
        items: selectedItems,
      });
      onCreated?.(response.data);
      onClose();
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Purchase Order could not be created from the Market List.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-w-5xl">
        <div className="border-b border-slate-200 px-6 py-5">
          <h2 className="text-xl font-semibold">Create PO from Market List</h2>
          <p className="mt-1 text-sm text-slate-500">Only approved, location-scoped Market Lists are available. Source lines remain traceable to the Market List.</p>
        </div>
        <div className="space-y-5 p-6">
          {error && <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</div>}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium">
              Approved Market List
              <select
                className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                value={marketListId ?? ""}
                onChange={(event) => setMarketListId(Number(event.target.value) || undefined)}
              >
                <option value="">Select Market List...</option>
                {(marketLists.data?.items ?? []).map((item: any) => (
                  <option key={item.id} value={item.id}>
                    {item.ml_number} — {item.location_name ?? "Location —"} — {item.department_name ?? "Department —"}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Supplier
              <select
                className="mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                value={supplierId ?? ""}
                onChange={(event) => setSupplierId(Number(event.target.value) || undefined)}
              >
                <option value="">Select supplier...</option>
                {(suppliers.data ?? []).map((supplier: any) => (
                  <option key={supplier.id} value={supplier.id}>{supplier.code} — {supplier.name}</option>
                ))}
              </select>
            </label>
          </div>

          {detail.data && (
            <div className="rounded-md border bg-slate-50 p-3 text-sm">
              <div className="grid gap-3 md:grid-cols-3">
                <div><span className="text-xs text-slate-500">Business Unit</span><div className="font-medium">{detail.data.business_unit_name ?? "—"}</div></div>
                <div><span className="text-xs text-slate-500">Department</span><div className="font-medium">{detail.data.department_name ?? "—"}</div></div>
                <div><span className="text-xs text-slate-500">Location</span><div className="font-medium">{detail.data.location_name ?? "—"}</div></div>
              </div>
            </div>
          )}

          {detail.data?.items?.length ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[760px] text-sm">
                <thead><tr className="border-b bg-slate-50 text-left"><th className="p-3">Item</th><th className="p-3">ML Qty</th><th className="p-3">PO Qty</th><th className="p-3">UOM</th><th className="p-3">Estimated Price</th></tr></thead>
                <tbody>
                  {detail.data.items.map((item: any) => {
                    const line = selected.find((entry) => entry.market_list_item_id === item.id);
                    return <tr key={item.id} className="border-t">
                      <td className="p-3">{item.product_code} — {item.product_name}</td>
                      <td>{item.quantity}</td>
                      <td><input type="number" min="0" step="0.01" max={item.quantity} className="h-9 w-28 rounded-md border px-2 text-right" value={line?.quantity ?? 0} onChange={(event) => updateQuantity(item.id, Number(event.target.value))}/></td>
                      <td>{item.uom ?? "—"}</td>
                      <td>{Number(item.estimated_price ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>;
                  })}
                </tbody>
              </table>
            </div>
          ) : marketListId ? <p className="text-sm text-slate-500">Loading Market List source lines...</p> : null}

          <div className="flex justify-end gap-3 border-t pt-4">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="button" loading={convert.isPending} onClick={submit}>Create Purchase Order</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

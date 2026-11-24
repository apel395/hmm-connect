import { useEffect, useMemo, useState } from "react";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import SearchableSelect from "@/components/form/SearchableSelect";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";

const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

function conversionMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return (error as { message?: string })?.message || "The Purchase Order could not be created.";
}

interface MarketListLine {
  id: number;
  product_code?: string | null;
  product_name?: string | null;
  uom?: string | null;
  quantity: number;
  estimated_price: number;
  tax_amount?: number | null;
  line_total?: number | null;
}

interface Props {
  open: boolean;
  marketList: {
    ml_number: string;
    total_amount?: number | null;
    items?: MarketListLine[];
    generated_purchase_orders?: Array<{ id: number; document_number: string; status: string }>;
  };
  onClose: () => void;
  onConvert: (items: undefined, supplierId: number) => Promise<void>;
}

export default function MarketListConvertDialog({ open, marketList, onClose, onConvert }: Props) {
  const suppliers = useSuppliers("", 100, open);
  const [supplierId, setSupplierId] = useState<number>();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const lines = useMemo(() => marketList.items ?? [], [marketList.items]);
  const alreadyConverted = (marketList.generated_purchase_orders ?? []).length > 0;

  useEffect(() => {
    if (open) {
      setSupplierId(undefined);
      setError("");
      setSaving(false);
    }
  }, [open]);

  const submit = async () => {
    if (!supplierId) {
      setError("Select the supplier for the Purchase Order.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      // Returning undefined lets the backend convert every remaining quantity and
      // protects partially converted Market Lists from stale client quantities.
      await onConvert(undefined, supplierId);
    } catch (failure) {
      setError(conversionMessage(failure));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => !saving && !value && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Purchase Order from {marketList.ml_number}</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {suppliers.isError && (
            <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              Suppliers could not be loaded.{" "}
              <button type="button" className="underline" onClick={() => void suppliers.refetch()}>Retry</button>
            </p>
          )}
          <div data-field="supplier_id">
            <SearchableSelect
              label="Supplier"
              value={supplierId}
              required
              disabled={suppliers.isLoading}
              placeholder={suppliers.isLoading ? "Loading suppliers…" : "Type supplier code or name..."}
              options={(suppliers.data ?? []).map((supplier: any) => ({
                id: supplier.id,
                label: `${supplier.code ?? ""}${supplier.code ? " — " : ""}${supplier.name}`,
                keywords: [supplier.code ?? "", supplier.name ?? ""],
              }))}
              onChange={setSupplierId}
            />
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
            The backend converts every remaining Market List quantity. The order is created as a Draft
            Purchase Order and still needs its normal approval before receiving.
            {alreadyConverted && " Items already converted to another Purchase Order are excluded automatically."}
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="p-2 text-left">Item</th>
                  <th>UOM</th>
                  <th className="text-right">Quantity</th>
                  <th className="text-right">Estimated Price</th>
                  <th className="text-right">PPN</th>
                  <th className="p-2 text-right">Line Total</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {lines.map((line) => (
                  <tr key={line.id}>
                    <td className="p-2">
                      <div className="font-medium">{line.product_name ?? "—"}</div>
                      <div className="text-xs text-slate-500">{line.product_code}</div>
                    </td>
                    <td>{line.uom ?? "—"}</td>
                    <td className="text-right tabular-nums">{line.quantity}</td>
                    <td className="text-right tabular-nums">{money(line.estimated_price)}</td>
                    <td className="text-right tabular-nums">{money(line.tax_amount)}</td>
                    <td className="p-2 text-right font-semibold tabular-nums">{money(line.line_total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50">
                <tr>
                  <td colSpan={5} className="p-2 text-right font-semibold">Market List Total</td>
                  <td className="p-2 text-right font-bold tabular-nums">{money(marketList.total_amount)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          {error && <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" disabled={saving} onClick={onClose}>Cancel</Button>
          <Button loading={saving} disabled={!supplierId} onClick={submit}>Create Purchase Order</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

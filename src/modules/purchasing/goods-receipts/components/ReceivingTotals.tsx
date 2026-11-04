interface ReceivingTotalsProps {
  subtotal: number;
  tax: number;
  label?: string;
}

const currency = (value: number) =>
  value.toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function ReceivingTotals({
  subtotal,
  tax,
  label = "Estimated PPN",
}: ReceivingTotalsProps) {
  return (
    <div className="ml-auto w-full max-w-xs rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs tabular-nums">
      <div className="flex items-center justify-between gap-5 text-slate-600">
        <span>Subtotal</span>
        <span>{currency(subtotal)}</span>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-5 text-slate-600">
        <span>{label}</span>
        <span>{currency(tax)}</span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-5 border-t border-slate-200 pt-2 text-sm font-semibold text-slate-900">
        <span>Grand Total</span>
        <span>{currency(subtotal + tax)}</span>
      </div>
    </div>
  );
}

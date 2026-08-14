import Card from "@/components/ui/Card";

interface Props {
  subtotal?: number;
  discount?: number;
  tax?: number;
  total: number;
}

const money = (value:number) => value.toLocaleString("en-US", { minimumFractionDigits:2, maximumFractionDigits:2 });

export default function PurchaseOrderSummary({ subtotal, discount = 0, tax = 0, total }: Props) {
  const base = subtotal ?? total + discount - tax;
  return <Card>
    <div className="grid gap-5 md:grid-cols-[1fr_320px] md:items-end">
      <div><div className="text-sm font-semibold text-slate-900">Purchase Order Value</div><div className="mt-1 text-xs text-slate-500">PPN is inherited per item from Item Master/PR and recalculated by the backend using the final PO price.</div></div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between text-slate-600"><span>Subtotal</span><span className="tabular-nums">{money(base)}</span></div>
        {discount > 0 && <div className="flex justify-between text-slate-600"><span>Discount</span><span className="tabular-nums">({money(discount)})</span></div>}
        <div className="flex justify-between text-slate-600"><span>PPN</span><span className="tabular-nums">{money(tax)}</span></div>
        <div className="flex justify-between border-t border-slate-200 pt-3 text-lg font-bold text-slate-900"><span>Grand Total</span><span className="tabular-nums">{money(total)}</span></div>
      </div>
    </div>
  </Card>;
}

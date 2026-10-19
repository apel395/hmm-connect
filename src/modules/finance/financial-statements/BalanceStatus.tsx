import { CircleCheck, CircleAlert } from "lucide-react";

export type BalanceControl = { difference: string | number; is_balanced: boolean };

export default function BalanceStatus({ control }: { control?: BalanceControl }) {
  if (!control) return null;
  const Icon = control.is_balanced ? CircleCheck : CircleAlert;
  const difference = Number(control.difference).toLocaleString("id-ID", { maximumFractionDigits: 2 });
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded px-2 py-1 text-xs font-semibold ${control.is_balanced ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`} aria-label="Balance sheet status">
    <Icon size={13} aria-hidden="true" />{control.is_balanced ? "Balanced" : `Out of balance · ${difference}`}
  </span>;
}

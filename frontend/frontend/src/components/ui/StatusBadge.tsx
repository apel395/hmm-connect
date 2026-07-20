interface StatusBadgeProps {
  status: string;
}

const styles: Record<string, string> = {
  APPROVED: "bg-emerald-50 text-emerald-700 ring-emerald-600/10",
  RECEIVED: "bg-emerald-50 text-emerald-700 ring-emerald-600/10",
  ACTIVE: "bg-emerald-50 text-emerald-700 ring-emerald-600/10",
  SUBMITTED: "bg-blue-50 text-blue-700 ring-blue-600/10",
  PARTIALLY_RECEIVED: "bg-blue-50 text-blue-700 ring-blue-600/10",
  CONVERTED: "bg-violet-50 text-violet-700 ring-violet-600/10",
  EXPIRED: "bg-amber-50 text-amber-700 ring-amber-600/10",
  REJECTED: "bg-red-50 text-red-700 ring-red-600/10",
  CANCELLED: "bg-red-50 text-red-700 ring-red-600/10",
  DRAFT: "bg-slate-100 text-slate-700 ring-slate-500/10",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${styles[status] ?? styles.DRAFT}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

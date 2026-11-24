import type { ReactNode } from "react";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import { purchasingStatusLabel, purchasingStatusVariant } from "./purchasingStatus";

export function PurchasingStatusBadge({
  value,
  label,
  className,
}: {
  value?: string | null;
  label?: string;
  className?: string;
}) {
  return (
    <Badge variant={purchasingStatusVariant(value)} className={className}>
      {label ?? purchasingStatusLabel(value)}
    </Badge>
  );
}

export function PurchasingDocumentHeader({
  eyebrow,
  number,
  status,
  statusLabel: customStatusLabel,
  meta,
  children,
  actions,
}: {
  eyebrow: string;
  number: string;
  status?: string | null;
  statusLabel?: string;
  meta?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-5 sm:px-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            {eyebrow}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-3">
            <h1 className="break-words text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              {number}
            </h1>
            {status && (
              <PurchasingStatusBadge value={status} label={customStatusLabel} />
            )}
          </div>
          {meta && (
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              {meta}
            </div>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2 print:hidden">{actions}</div>
        )}
      </div>
      {children && <div className="px-5 py-5 sm:px-6">{children}</div>}
    </div>
  );
}

export function PurchasingMetaGrid({ children }: { children: ReactNode }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {children}
    </dl>
  );
}

export function PurchasingMetaItem({
  label,
  children,
  className,
}: {
  label: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`min-w-0 ${className ?? ""}`}>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd className="mt-1 truncate text-sm font-medium text-slate-800">
        {children ?? "—"}
      </dd>
    </div>
  );
}

export function PurchasingSection({
  title,
  description,
  actions,
  children,
  flush = false,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3.5">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {description && (
            <p className="mt-0.5 text-xs text-slate-500">{description}</p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className={flush ? "" : "p-5"}>{children}</div>
    </Card>
  );
}

export function PurchasingTotals({
  rows,
}: {
  rows: Array<{ label: string; value: ReactNode; emphasis?: boolean }>;
}) {
  return (
    <div className="border-t border-slate-200 bg-slate-50 px-5 py-4">
      <dl className="ml-auto w-full max-w-sm space-y-2 text-sm">
        {rows.map((row) => (
          <div
            key={row.label}
            className={`flex items-center justify-between gap-8 ${
              row.emphasis
                ? "border-t border-slate-200 pt-2 text-base font-bold text-slate-900"
                : "text-slate-600"
            }`}
          >
            <dt>{row.label}</dt>
            <dd className="tabular-nums">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function PurchasingNote({
  title = "Notes",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  const hasValue =
    typeof children === "string"
      ? children.trim().length > 0
      : children !== null && children !== undefined && children !== false;
  if (!hasValue) return null;

  return (
    <Card className="p-5">
      <h3 className="mb-2 text-sm font-semibold text-slate-900">{title}</h3>
      <p className="whitespace-pre-wrap text-sm text-slate-600">{children}</p>
    </Card>
  );
}

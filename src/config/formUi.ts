export type FormDensity = "compact" | "standard" | "comfortable";

export const FORM_UI = {
  defaultDensity: "compact" as FormDensity,
  density: {
    compact: {
      control: "h-9 px-3 py-2 text-[13px]",
      textarea: "min-h-20 px-3 py-2 text-[13px]",
      label: "mb-1.5 text-xs",
      fieldGap: "gap-3",
      sectionGap: "space-y-4",
    },
    standard: {
      control: "h-10 px-3 py-2 text-[13px]",
      textarea: "min-h-24 px-3 py-2.5 text-[13px]",
      label: "mb-2 text-[13px]",
      fieldGap: "gap-4",
      sectionGap: "space-y-5",
    },
    comfortable: {
      control: "h-11 px-3.5 py-2.5 text-sm",
      textarea: "min-h-28 px-3.5 py-3 text-sm",
      label: "mb-2 text-sm",
      fieldGap: "gap-5",
      sectionGap: "space-y-6",
    },
  },
  controlBase:
    "w-full rounded-md border border-slate-300 bg-white text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500",
  error:
    "border-red-500 focus:border-red-500 focus:ring-red-500/20",
  label: "inline-flex items-center gap-1 font-medium text-slate-700",
  helpText: "mt-1 text-[11px] leading-4 text-slate-500",
  errorText: "mt-1 text-[11px] leading-4 text-red-600",
  grid: "grid grid-cols-1 gap-3 md:grid-cols-2",
  section:
    "rounded-lg border border-slate-200 bg-white p-4",
  sectionTitle:
    "mb-3 text-xs font-semibold uppercase tracking-[0.04em] text-slate-600",
  dialog: {
    header: "shrink-0 border-b border-slate-200 px-5 py-3.5 pr-12",
    body: "min-h-0 flex-1 overflow-y-auto px-5 py-4 text-[13px]",
    footer:
      "shrink-0 flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 bg-slate-50/70 px-5 py-3",
  },
} as const;

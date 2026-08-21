export type TableDensity = "compact" | "standard" | "comfortable";

export const TABLE_UI = {
  defaultDensity: "compact" as TableDensity,
  density: {
    compact: {
      table: "text-xs",
      headerCell: "h-9 px-4 py-2.5",
      bodyCell: "px-4 py-2.5",
    },
    standard: {
      table: "text-[13px]",
      headerCell: "h-10 px-4 py-3",
      bodyCell: "px-4 py-3",
    },
    comfortable: {
      table: "text-sm",
      headerCell: "h-11 px-5 py-3.5",
      bodyCell: "px-5 py-3.5",
    },
  },
  header: "text-[11px] font-semibold uppercase tracking-[0.04em] text-slate-600",
  secondaryText: "text-[11px] text-slate-400",
  documentLink: "font-medium text-emerald-700 hover:underline",
  numeric: "text-right tabular-nums",
} as const;

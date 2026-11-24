import { FORM_UI } from "@/config/formUi";

/** One consistent standard-size control for purchasing dialogs. */
export const PURCHASING_FIELD = `${FORM_UI.controlBase} !h-10 !rounded-lg !px-3 !text-[13px]`;

/** Consistent multiline control for notes and reasons. */
export const PURCHASING_TEXTAREA = `${FORM_UI.controlBase} !min-h-24 !rounded-lg !px-3 !py-2.5 !text-[13px]`;

/** Compact numeric control used inside editable line grids. */
export const PURCHASING_LINE_INPUT = `${FORM_UI.controlBase} !h-9 !rounded-lg !px-2 !text-[13px] !tabular-nums`;

/** Small numeric control for percentages and short values. */
export const PURCHASING_SMALL_INPUT = `${FORM_UI.controlBase} !h-9 !w-20 !rounded-lg !px-2 !text-right !text-[13px] !tabular-nums`;

export const PURCHASING_LABEL = "text-xs font-semibold uppercase tracking-wide text-slate-500";

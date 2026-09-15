import Button from "@/components/ui/Button";

type DateRangeFilterProps = {
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  onApply: () => void;
  onClear: () => void;
  fromLabel?: string;
  toLabel?: string;
};

const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function DateRangeFilter({
  from,
  to,
  onFromChange,
  onToChange,
  onApply,
  onClear,
  fromLabel = "From Date",
  toLabel = "To Date",
}: DateRangeFilterProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex min-w-[150px] flex-1 flex-col gap-1 text-xs font-medium text-slate-600">
        {fromLabel}
        <input type="date" className={input} value={from} max={to || undefined} onChange={(event) => onFromChange(event.target.value)} />
      </label>
      <label className="flex min-w-[150px] flex-1 flex-col gap-1 text-xs font-medium text-slate-600">
        {toLabel}
        <input type="date" className={input} value={to} min={from || undefined} onChange={(event) => onToChange(event.target.value)} />
      </label>
      <div className="flex gap-2">
        <Button onClick={onApply}>Apply</Button>
        <Button variant="outline" onClick={onClear}>Clear</Button>
      </div>
    </div>
  );
}

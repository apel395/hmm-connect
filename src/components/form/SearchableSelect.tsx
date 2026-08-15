import { useEffect, useId, useMemo, useState } from "react";

export interface SearchableSelectOption {
  id: number;
  label: string;
  keywords?: string[];
}

interface Props {
  label?: string;
  value?: number;
  options: SearchableSelectOption[];
  disabled?: boolean;
  placeholder?: string;
  required?: boolean;
  className?: string;
  onChange: (value: number | undefined) => void;
}

export default function SearchableSelect({
  label,
  value,
  options,
  disabled = false,
  placeholder = "Type to search...",
  required = false,
  className = "",
  onChange,
}: Props) {
  const listId = useId();
  const selected = options.find((option) => option.id === value);
  const [query, setQuery] = useState(selected?.label ?? "");

  useEffect(() => {
    setQuery(selected?.label ?? "");
  }, [selected?.id, selected?.label]);

  const optionMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const option of options) {
      map.set(option.label.trim().toLowerCase(), option.id);
      for (const keyword of option.keywords ?? []) {
        const normalized = keyword.trim().toLowerCase();
        if (normalized) map.set(normalized, option.id);
      }
    }
    return map;
  }, [options]);

  const commit = (raw: string) => {
    const normalized = raw.trim().toLowerCase();
    if (!normalized) {
      onChange(undefined);
      return;
    }
    const nextId = optionMap.get(normalized);
    if (!nextId) return;
    onChange(nextId);
    const next = options.find((option) => option.id === nextId);
    if (next) setQuery(next.label);
  };

  return (
    <label className="block text-sm font-medium">
      {label && <span>{label}{required ? " *" : ""}</span>}
      <div className={label ? "mt-1" : ""}>
        <input
          type="text"
          list={listId}
          value={query}
          disabled={disabled}
          required={required}
          placeholder={placeholder}
          autoComplete="off"
          className={`h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-[#0F6758] focus:ring-2 focus:ring-[#0F6758]/20 disabled:bg-slate-100 ${className}`}
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => {
            const next = event.target.value;
            setQuery(next);
            commit(next);
          }}
          onBlur={(event) => {
            const raw = event.currentTarget.value.trim();
            const exactId = optionMap.get(raw.toLowerCase());
            if (!raw) {
              setQuery("");
              onChange(undefined);
              return;
            }
            if (!exactId) setQuery(selected?.label ?? "");
          }}
        />
        <datalist id={listId}>
          {options.map((option) => (
            <option key={option.id} value={option.label} />
          ))}
        </datalist>
      </div>
    </label>
  );
}

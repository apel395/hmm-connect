import { createPortal } from "react-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FORM_UI } from "@/config/formUi";

export interface SearchableSelectOption {
  id: number;
  label?: string;
  code?: string;
  name?: string;
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

type DropdownPosition = {
  left: number;
  top: number;
  width: number;
};

function optionLabel(option: SearchableSelectOption): string {
  if (option.label?.trim()) return option.label.trim();
  const code = option.code?.trim() ?? "";
  const name = option.name?.trim() ?? "";
  if (code && name) return `${code} - ${name}`;
  return name || code || String(option.id);
}

function searchableText(option: SearchableSelectOption): string {
  return [optionLabel(option), option.code, option.name, ...(option.keywords ?? [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
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
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selected = options.find((option) => option.id === value);
  const selectedLabel = selected ? optionLabel(selected) : "";
  const [query, setQuery] = useState(selectedLabel);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [position, setPosition] = useState<DropdownPosition | null>(null);

  useEffect(() => {
    if (!open) setQuery(selectedLabel);
  }, [selectedLabel, open]);

  const updatePosition = useCallback(() => {
    const input = inputRef.current;
    if (!input) return;
    const rect = input.getBoundingClientRect();
    setPosition({ left: rect.left, top: rect.bottom + 4, width: rect.width });
  }, []);

  const filteredOptions = useMemo(() => {
    const raw = query.trim().toLowerCase();
    const effective = selected && raw === selectedLabel.toLowerCase() ? "" : raw;
    if (!effective) return options.slice(0, 50);
    return options.filter((option) => searchableText(option).includes(effective)).slice(0, 50);
  }, [options, query, selected, selectedLabel]);

  useEffect(() => {
    if (!open || filteredOptions.length === 0) {
      setActiveIndex(-1);
      return;
    }
    setActiveIndex((current) => current >= 0 && current < filteredOptions.length ? current : 0);
  }, [open, filteredOptions]);

  useEffect(() => {
    if (activeIndex >= 0) optionRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const reposition = () => updatePosition();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      const insideInput = rootRef.current?.contains(target);
      const insideDropdown = dropdownRef.current?.contains(target);
      if (!insideInput && !insideDropdown) setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  const selectOption = useCallback((option: SearchableSelectOption) => {
    onChange(option.id);
    setQuery(optionLabel(option));
    setOpen(false);
    setActiveIndex(-1);
  }, [onChange]);

  const moveActive = (direction: 1 | -1) => {
    if (filteredOptions.length === 0) return;
    setOpen(true);
    setActiveIndex((current) => {
      if (current < 0) return direction === 1 ? 0 : filteredOptions.length - 1;
      return (current + direction + filteredOptions.length) % filteredOptions.length;
    });
  };

  const dropdown = open && !disabled && position && typeof document !== "undefined"
    ? createPortal(
        <div
          ref={dropdownRef}
          role="listbox"
          className="pointer-events-auto fixed z-[10000] max-h-64 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-xl"
          style={{ left: position.left, top: position.top, width: position.width }}
        >
          {filteredOptions.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-500">No matching options.</div>
          ) : filteredOptions.map((option, index) => (
            <button
              key={option.id}
              ref={(element) => { optionRefs.current[index] = element; }}
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              className={`pointer-events-auto block w-full border-b border-slate-100 px-3 py-2 text-left text-[13px] last:border-b-0 focus:outline-none ${index === activeIndex ? "bg-emerald-50 text-slate-900" : "bg-white text-slate-800 hover:bg-emerald-50"}`}
              onMouseEnter={() => setActiveIndex(index)}
              onPointerDown={(event) => {
                event.preventDefault();
                event.stopPropagation();
                selectOption(option);
              }}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                selectOption(option);
              }}
            >
              {optionLabel(option)}
            </button>
          ))}
        </div>,
        document.body,
      )
    : null;

  return (
    <label className="block">
      {label && <span className={`${FORM_UI.label} ${FORM_UI.density.compact.label}`}>{label}{required ? <span className="text-red-500"> *</span> : null}</span>}
      <div ref={rootRef} className={`relative ${label ? "mt-1" : ""}`}>
        <input
          ref={inputRef}
          type="text"
          value={query}
          disabled={disabled}
          required={required}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-autocomplete="list"
          data-form-control
          data-form-density="compact"
          className={`${FORM_UI.controlBase} ${FORM_UI.density.compact.control} ${className}`}
          onFocus={(event) => {
            updatePosition();
            setOpen(true);
            event.currentTarget.select();
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            updatePosition();
            setOpen(true);
            setActiveIndex(0);
            if (!event.target.value.trim() && value !== undefined) onChange(undefined);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              moveActive(1);
              return;
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              moveActive(-1);
              return;
            }
            if (event.key === "Home" && open && filteredOptions.length > 0) {
              event.preventDefault();
              setActiveIndex(0);
              return;
            }
            if (event.key === "End" && open && filteredOptions.length > 0) {
              event.preventDefault();
              setActiveIndex(filteredOptions.length - 1);
              return;
            }
            if (event.key === "Enter" && open && activeIndex >= 0 && filteredOptions[activeIndex]) {
              event.preventDefault();
              selectOption(filteredOptions[activeIndex]);
              return;
            }
            if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
              setQuery(selectedLabel);
            }
          }}
          onBlur={() => {
            window.setTimeout(() => {
              if (!dropdownRef.current?.matches(":hover")) {
                setQuery(selectedLabel);
              }
            }, 0);
          }}
        />
        {dropdown}
      </div>
    </label>
  );
}

import { createPortal } from "react-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { productApi } from "@/modules/master/products/api/productApi";

export interface ProductComboboxOption {
  id: number;
  code?: string;
  product_code?: string;
  name?: string;
  product_name?: string;
  description?: string | null;
  uom?: string;
  usage_uom?: string;
  tax_category?: string;
  is_taxable?: boolean;
  tax_rate?: number | string;
}

interface Props {
  value?: number;
  products?: ProductComboboxOption[];
  disabled?: boolean;
  placeholder?: string;
  remote?: boolean;
  marketOnly?: boolean;
  onChange: (productId: number) => void;
  onSelect?: (product: ProductComboboxOption) => void;
}

type DropdownPosition = {
  left: number;
  top: number;
  width: number;
};

function labelFor(product: ProductComboboxOption): string {
  const code = product.code ?? product.product_code ?? "";
  const name = product.name ?? product.product_name ?? "";
  return code ? `${code} - ${name}` : name;
}

async function loadRemoteProducts(search: string, marketOnly: boolean): Promise<ProductComboboxOption[]> {
  try {
    const lookup = await productApi.lookup(search, 30, marketOnly);
    if (Array.isArray(lookup.data) && lookup.data.length > 0) return lookup.data;
  } catch {
    // Fall through to canonical pagination endpoint.
  }

  const list = await productApi.list({ page: 1, page_size: 30, search, active_only: true, market_only: marketOnly });
  const payload = list.data;
  if (Array.isArray(payload)) return payload;
  return Array.isArray(payload?.items) ? payload.items : [];
}

export default function ProductCombobox({
  value,
  products = [],
  disabled,
  placeholder = "Type product code or name...",
  remote = false,
  marketOnly = false,
  onChange,
  onSelect,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const requestIdRef = useRef(0);
  const [remoteProducts, setRemoteProducts] = useState<ProductComboboxOption[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [position, setPosition] = useState<DropdownPosition | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const options = remote ? remoteProducts : products;
  const selected = [...products, ...remoteProducts].find((product) => product.id === value);
  const [query, setQuery] = useState(selected ? labelFor(selected) : "");

  const updatePosition = useCallback(() => {
    const input = inputRef.current;
    if (!input) return;
    const rect = input.getBoundingClientRect();
    setPosition({ left: rect.left, top: rect.bottom + 4, width: rect.width });
  }, []);

  useEffect(() => {
    setQuery(selected ? labelFor(selected) : "");
  }, [selected]);

  useEffect(() => {
    if (!remote || disabled) return;
    const raw = query.trim();
    const selectedLabel = selected ? labelFor(selected) : "";
    if (selected && raw === selectedLabel && remoteProducts.length > 0) return;

    const requestId = ++requestIdRef.current;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setLoadError(false);
      try {
        const rows = await loadRemoteProducts(selected && raw === selectedLabel ? "" : raw, marketOnly);
        if (requestId === requestIdRef.current) setRemoteProducts(rows);
      } catch {
        if (requestId === requestIdRef.current) {
          setRemoteProducts([]);
          setLoadError(true);
        }
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    }, raw ? 250 : 0);

    return () => window.clearTimeout(timer);
  }, [remote, disabled, query, selected, remoteProducts.length, marketOnly]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const onReposition = () => updatePosition();
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      const insideInput = rootRef.current?.contains(target);
      const insideDropdown = dropdownRef.current?.contains(target);
      if (!insideInput && !insideDropdown) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const visibleOptions = useMemo(() => options.slice(0, 30), [options]);

  useEffect(() => {
    if (!open || visibleOptions.length === 0) {
      setActiveIndex(-1);
      return;
    }
    setActiveIndex((current) => current >= 0 && current < visibleOptions.length ? current : 0);
  }, [open, visibleOptions]);

  useEffect(() => {
    if (activeIndex < 0) return;
    optionRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const selectProduct = useCallback((product: ProductComboboxOption) => {
    onChange(product.id);
    onSelect?.(product);
    setQuery(labelFor(product));
    setOpen(false);
    setActiveIndex(-1);
  }, [onChange, onSelect]);

  const moveActive = (direction: 1 | -1) => {
    if (visibleOptions.length === 0) return;
    setOpen(true);
    setActiveIndex((current) => {
      if (current < 0) return direction === 1 ? 0 : visibleOptions.length - 1;
      return (current + direction + visibleOptions.length) % visibleOptions.length;
    });
  };

  const dropdown = open && !disabled && position && typeof document !== "undefined"
    ? createPortal(
        <div
          ref={dropdownRef}
          role="listbox"
          className="pointer-events-auto fixed z-[10000] max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-xl"
          style={{ left: position.left, top: position.top, width: position.width }}
        >
          {loading && visibleOptions.length === 0 ? (
            <div className="px-3 py-3 text-sm text-slate-500">Loading items...</div>
          ) : loadError ? (
            <div className="px-3 py-3 text-sm text-red-600">Unable to load items. Please try again.</div>
          ) : visibleOptions.length === 0 ? (
            <div className="px-3 py-3 text-sm text-slate-500">No matching items.</div>
          ) : (
            visibleOptions.map((product, index) => (
              <button
                key={product.id}
                ref={(element) => { optionRefs.current[index] = element; }}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={`pointer-events-auto block w-full border-b border-slate-100 px-3 py-2 text-left last:border-b-0 focus:outline-none ${index === activeIndex ? "bg-emerald-50" : "hover:bg-emerald-50"}`}
                onMouseEnter={() => setActiveIndex(index)}
                onPointerDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  selectProduct(product);
                }}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  selectProduct(product);
                }}
              >
                <div className="text-sm font-medium text-slate-800">{labelFor(product)}</div>
                {(product.uom || product.usage_uom) && (
                  <div className="mt-0.5 text-xs text-slate-500">
                    UOM: {product.uom ?? "—"}{product.usage_uom ? ` · Usage: ${product.usage_uom}` : ""}
                  </div>
                )}
              </button>
            ))
          )}
        </div>,
        document.body,
      )
    : null;

  return (
    <div ref={rootRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
        aria-expanded={open}
        aria-autocomplete="list"
        className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-[#0F6758] focus:ring-2 focus:ring-[#0F6758]/20 disabled:bg-slate-100"
        onFocus={() => {
          updatePosition();
          setOpen(true);
        }}
        onChange={(event) => {
          const next = event.target.value;
          setQuery(next);
          updatePosition();
          setOpen(true);
          setActiveIndex(0);
          if (!next.trim() && value) onChange(0);
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
          if (event.key === "Home" && open && visibleOptions.length > 0) {
            event.preventDefault();
            setActiveIndex(0);
            return;
          }
          if (event.key === "End" && open && visibleOptions.length > 0) {
            event.preventDefault();
            setActiveIndex(visibleOptions.length - 1);
            return;
          }
          if (event.key === "Enter" && open && activeIndex >= 0 && visibleOptions[activeIndex]) {
            event.preventDefault();
            selectProduct(visibleOptions[activeIndex]);
            return;
          }
          if (event.key === "Escape") {
            event.preventDefault();
            setOpen(false);
            setActiveIndex(-1);
          }
        }}
      />
      {dropdown}
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
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
  onChange: (productId: number) => void;
  onSelect?: (product: ProductComboboxOption) => void;
}

function labelFor(product: ProductComboboxOption): string {
  const code = product.code ?? product.product_code ?? "";
  const name = product.name ?? product.product_name ?? "";
  return code ? `${code} - ${name}` : name;
}

async function loadRemoteProducts(search: string): Promise<ProductComboboxOption[]> {
  try {
    const lookup = await productApi.lookup(search, 30);
    if (Array.isArray(lookup.data) && lookup.data.length > 0) return lookup.data;
  } catch {
    // Fall through to the canonical paginated endpoint. This also keeps the
    // create forms usable while an older API deployment is still warming up.
  }

  const list = await productApi.list({ page: 1, page_size: 30, search, active_only: true });
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
  onChange,
  onSelect,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const requestIdRef = useRef(0);
  const [remoteProducts, setRemoteProducts] = useState<ProductComboboxOption[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const options = remote ? remoteProducts : products;
  const selected = [...products, ...remoteProducts].find((product) => product.id === value);
  const [query, setQuery] = useState(selected ? labelFor(selected) : "");

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
        const rows = await loadRemoteProducts(selected && raw === selectedLabel ? "" : raw);
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
  }, [remote, disabled, query, selected, remoteProducts.length]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const visibleOptions = useMemo(() => options.slice(0, 30), [options]);

  const selectProduct = (product: ProductComboboxOption) => {
    onChange(product.id);
    onSelect?.(product);
    setQuery(labelFor(product));
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <input
        type="text"
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
        className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-[#0F6758] focus:ring-2 focus:ring-[#0F6758]/20 disabled:bg-slate-100"
        onFocus={() => setOpen(true)}
        onChange={(event) => {
          const next = event.target.value;
          setQuery(next);
          setOpen(true);
          if (!next.trim() && value) onChange(0);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
          if (event.key === "Enter" && open && visibleOptions.length === 1) {
            event.preventDefault();
            selectProduct(visibleOptions[0]);
          }
        }}
      />

      {open && !disabled && (
        <div className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {loading && visibleOptions.length === 0 ? (
            <div className="px-3 py-3 text-sm text-slate-500">Loading items...</div>
          ) : loadError ? (
            <div className="px-3 py-3 text-sm text-red-600">Unable to load items. Please try again.</div>
          ) : visibleOptions.length === 0 ? (
            <div className="px-3 py-3 text-sm text-slate-500">No matching items.</div>
          ) : (
            visibleOptions.map((product) => (
              <button
                key={product.id}
                type="button"
                className="block w-full border-b border-slate-100 px-3 py-2 text-left last:border-b-0 hover:bg-emerald-50 focus:bg-emerald-50 focus:outline-none"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectProduct(product)}
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
        </div>
      )}
    </div>
  );
}

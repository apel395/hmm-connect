import { useEffect, useId, useMemo, useState } from "react";
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

export default function ProductCombobox({
  value,
  products = [],
  disabled,
  placeholder = "Type product code or name...",
  remote = false,
  onChange,
  onSelect,
}: Props) {
  const listId = useId();
  const [remoteProducts, setRemoteProducts] = useState<ProductComboboxOption[]>([]);
  const options = remote ? remoteProducts : products;
  const selected = [...products, ...remoteProducts].find((product) => product.id === value);
  const [query, setQuery] = useState(selected ? labelFor(selected) : "");

  useEffect(() => {
    setQuery(selected ? labelFor(selected) : "");
  }, [selected?.id, selected?.code, selected?.product_code, selected?.name, selected?.product_name]);

  useEffect(() => {
    if (!remote || disabled) return;
    const raw = query.trim();
    const selectedLabel = selected ? labelFor(selected) : "";
    if (selected && raw === selectedLabel) return;
    const timer = window.setTimeout(async () => {
      try {
        const response = await productApi.lookup(raw, 30);
        setRemoteProducts(Array.isArray(response.data) ? response.data : []);
      } catch {
        setRemoteProducts([]);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [remote, disabled, query, selected?.id]);

  const labels = useMemo(
    () => new Map(options.map((product) => [labelFor(product).toLowerCase(), product])),
    [options],
  );

  const commit = (raw: string) => {
    const product = labels.get(raw.trim().toLowerCase());
    if (product) {
      onChange(product.id);
      onSelect?.(product);
      setQuery(labelFor(product));
      return;
    }
    if (!raw.trim()) onChange(0);
  };

  return (
    <div className="relative">
      <input
        type="text"
        list={listId}
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
        className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-[#0F6758] focus:ring-2 focus:ring-[#0F6758]/20 disabled:bg-slate-100"
        onFocus={(event) => event.currentTarget.select()}
        onChange={(event) => {
          const next = event.target.value;
          setQuery(next);
          commit(next);
        }}
        onBlur={(event) => {
          const raw = event.currentTarget.value;
          const product = labels.get(raw.trim().toLowerCase());
          if (!product && selected) setQuery(labelFor(selected));
          if (!product && !selected && !raw.trim()) setQuery("");
        }}
      />
      <datalist id={listId}>
        {options.map((product) => <option key={product.id} value={labelFor(product)} />)}
      </datalist>
    </div>
  );
}

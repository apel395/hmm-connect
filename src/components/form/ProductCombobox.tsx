import { useId, useMemo, useState } from "react";

export interface ProductComboboxOption {
  id: number;
  code?: string;
  product_code?: string;
  name?: string;
  product_name?: string;
}

interface Props {
  value?: number;
  products: ProductComboboxOption[];
  disabled?: boolean;
  placeholder?: string;
  onChange: (productId: number) => void;
}

function labelFor(product: ProductComboboxOption): string {
  const code = product.code ?? product.product_code ?? "";
  const name = product.name ?? product.product_name ?? "";
  return code ? `${code} - ${name}` : name;
}

export default function ProductCombobox({
  value,
  products,
  disabled,
  placeholder = "Type product code or name...",
  onChange,
}: Props) {
  const listId = useId();
  const selected = products.find((product) => product.id === value);
  const [query, setQuery] = useState(selected ? labelFor(selected) : "");

  const labels = useMemo(
    () => new Map(products.map((product) => [labelFor(product).toLowerCase(), product.id])),
    [products],
  );

  const commit = (raw: string) => {
    const nextId = labels.get(raw.trim().toLowerCase());
    if (nextId) {
      onChange(nextId);
      const product = products.find((item) => item.id === nextId);
      setQuery(product ? labelFor(product) : raw);
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
          const id = labels.get(raw.trim().toLowerCase());
          if (!id && selected) setQuery(labelFor(selected));
          if (!id && !selected && !raw.trim()) setQuery("");
        }}
      />
      <datalist id={listId}>
        {products.map((product) => (
          <option key={product.id} value={labelFor(product)} />
        ))}
      </datalist>
    </div>
  );
}

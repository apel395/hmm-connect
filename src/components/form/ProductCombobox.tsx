import { createPortal } from "react-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import Dialog, { DialogContent } from "@/components/ui/Dialog";
import { productApi } from "@/modules/master/products/api/productApi";
import { FORM_UI } from "@/config/formUi";
import useAuthorization from "@/hooks/useAuthorization";

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
  last_purchase_price?: number | string | null;
  last_purchase_date?: string | null;
  last_purchase_po_number?: string | null;
}

interface Props {
  value?: number;
  products?: ProductComboboxOption[];
  disabled?: boolean;
  placeholder?: string;
  remote?: boolean;
  marketOnly?: boolean;
  excludeMarket?: boolean;
  requireTaxReady?: boolean;
  onChange: (productId: number) => void;
  onSelect?: (product: ProductComboboxOption) => void;
}

type DropdownPosition = { left: number; top: number; width: number };
type TaxEditorState = { product: ProductComboboxOption; category: "STANDARD" | "EXEMPT" | "NON_VAT" | "SPECIAL"; rate: number; reason: string; reference: string };

function labelFor(product: ProductComboboxOption): string {
  const code = product.code ?? product.product_code ?? "";
  const name = product.name ?? product.product_name ?? "";
  return code ? `${code} - ${name}` : name;
}
function taxProfileIncomplete(product: ProductComboboxOption): boolean { return product.tax_category === "REVIEW_REQUIRED"; }
async function loadRemoteProducts(search: string, marketOnly: boolean, excludeMarket: boolean): Promise<ProductComboboxOption[]> {
  try {
    const lookup = await productApi.lookup(search, 30, marketOnly, excludeMarket);
    if (Array.isArray(lookup.data) && lookup.data.length > 0) return lookup.data;
  } catch {
    // Fall through to canonical pagination endpoint.
  }
  const list = await productApi.list({ page: 1, page_size: 30, search, active_only: true, market_only: marketOnly, exclude_market: excludeMarket });
  const payload = list.data;
  if (Array.isArray(payload)) return payload;
  return Array.isArray(payload?.items) ? payload.items : [];
}

export default function ProductCombobox({ value, products = [], disabled, placeholder = "Type product code or name...", remote = false, marketOnly = false, excludeMarket = false, requireTaxReady = false, onChange, onSelect }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const requestIdRef = useRef(0);
  const positionRef = useRef<DropdownPosition | null>(null);
  const repositionFrameRef = useRef<number | null>(null);
  const { hasPermission } = useAuthorization();
  const canManageTax = hasPermission("products.manage");
  const [remoteProducts, setRemoteProducts] = useState<ProductComboboxOption[]>([]);
  const [taxOverrides, setTaxOverrides] = useState<Record<number, ProductComboboxOption>>({});
  const [taxEditor, setTaxEditor] = useState<TaxEditorState | null>(null);
  const [taxSaving, setTaxSaving] = useState(false);
  const [taxError, setTaxError] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [position, setPosition] = useState<DropdownPosition | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [hoverIndex, setHoverIndex] = useState(-1);
  const withTaxOverride = useCallback((product: ProductComboboxOption) => ({ ...product, ...(taxOverrides[product.id] ?? {}) }), [taxOverrides]);
  const options = useMemo(() => (remote ? remoteProducts : products).map(withTaxOverride), [remote, remoteProducts, products, withTaxOverride]);
  const selected = useMemo(() => [...products, ...remoteProducts].map(withTaxOverride).find((product) => product.id === value), [products, remoteProducts, withTaxOverride, value]);
  const selectedLabel = selected ? labelFor(selected) : "";
  const [query, setQuery] = useState(selectedLabel);
  const hasRemoteProducts = remoteProducts.length > 0;

  const updatePosition = useCallback(() => {
    const input = inputRef.current;
    if (!input) return;
    const rect = input.getBoundingClientRect();
    const next = { left: rect.left, top: rect.bottom + 4, width: rect.width };
    const previous = positionRef.current;
    if (previous && previous.left === next.left && previous.top === next.top && previous.width === next.width) return;
    positionRef.current = next;
    setPosition(next);
  }, []);

  useEffect(() => { setQuery(selectedLabel); }, [selectedLabel]);

  useEffect(() => {
    if (!remote || disabled) return;
    const raw = query.trim();
    if (selected && raw === selectedLabel && hasRemoteProducts) return;
    const requestId = ++requestIdRef.current;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setLoadError(false);
      try {
        const rows = await loadRemoteProducts(selected && raw === selectedLabel ? "" : raw, marketOnly, excludeMarket);
        if (requestId === requestIdRef.current) setRemoteProducts(rows);
      } catch {
        if (requestId === requestIdRef.current) { setRemoteProducts([]); setLoadError(true); }
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    }, raw ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [remote, disabled, query, selected, selectedLabel, marketOnly, excludeMarket, hasRemoteProducts]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const scheduleReposition = () => {
      if (repositionFrameRef.current !== null) return;
      repositionFrameRef.current = window.requestAnimationFrame(() => {
        repositionFrameRef.current = null;
        updatePosition();
      });
    };
    window.addEventListener("resize", scheduleReposition);
    window.addEventListener("scroll", scheduleReposition, true);
    return () => {
      window.removeEventListener("resize", scheduleReposition);
      window.removeEventListener("scroll", scheduleReposition, true);
      if (repositionFrameRef.current !== null) {
        window.cancelAnimationFrame(repositionFrameRef.current);
        repositionFrameRef.current = null;
      }
    };
  }, [open, updatePosition]);

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target) && !dropdownRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);
  const visibleOptions = useMemo(() => options.slice(0, 30), [options]);
  useEffect(() => {
    if (!open || visibleOptions.length === 0) { setActiveIndex(-1); setHoverIndex(-1); return; }
    setActiveIndex((current) => current >= 0 && current < visibleOptions.length ? current : 0);
  }, [open, visibleOptions]);
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setOpen(false); setActiveIndex(-1); setHoverIndex(-1); } };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [open]);
  const scrollOptionIntoView = useCallback((index: number) => { if (index >= 0) optionRefs.current[index]?.scrollIntoView({ block: "nearest" }); }, []);

  const openTaxEditor = useCallback((product: ProductComboboxOption) => {
    const currentCategory = product.tax_category && product.tax_category !== "REVIEW_REQUIRED" ? product.tax_category : "STANDARD";
    setTaxError("");
    setTaxEditor({ product, category: currentCategory as TaxEditorState["category"], rate: Number(product.tax_rate || 0), reason: "", reference: "" });
  }, []);
  const selectProduct = useCallback((product: ProductComboboxOption) => {
    if (requireTaxReady && taxProfileIncomplete(product)) {
      setOpen(false); setActiveIndex(-1); setHoverIndex(-1);
      if (canManageTax) { openTaxEditor(product); return; }
      toast.error("This item's PPN profile must be completed by an authorized Item Master user before it can be used.");
      return;
    }
    onChange(product.id); onSelect?.(product); setQuery(labelFor(product)); setOpen(false); setActiveIndex(-1); setHoverIndex(-1);
  }, [onChange, onSelect, requireTaxReady, canManageTax, openTaxEditor]);
  const saveTaxProfile = useCallback(async () => {
    if (!taxEditor) return;
    const taxable = taxEditor.category === "STANDARD" || taxEditor.category === "SPECIAL";
    if (taxable && (!Number.isFinite(taxEditor.rate) || taxEditor.rate <= 0)) { setTaxError("PPN rate must be greater than zero."); return; }
    setTaxSaving(true); setTaxError("");
    try {
      const response = await productApi.updateTaxProfile(taxEditor.product.id, { tax_category: taxEditor.category, is_taxable: taxable, tax_rate: taxable ? taxEditor.rate : 0, tax_reason: taxEditor.reason.trim() || null, tax_reference: taxEditor.reference.trim() || null });
      const patch = (response.data ?? {}) as Partial<ProductComboboxOption>;
      const updated = { ...taxEditor.product, ...patch, tax_category: patch.tax_category ?? taxEditor.category, is_taxable: patch.is_taxable !== undefined ? Boolean(patch.is_taxable) : taxable, tax_rate: Number(patch.tax_rate ?? (taxable ? taxEditor.rate : 0)) } as ProductComboboxOption;
      setTaxOverrides((current) => ({ ...current, [updated.id]: updated }));
      setRemoteProducts((current) => current.map((product) => product.id === updated.id ? { ...product, ...updated } : product));
      onChange(updated.id); onSelect?.(updated); setQuery(labelFor(updated)); setTaxEditor(null); setOpen(false); setActiveIndex(-1); setHoverIndex(-1);
    } catch { setTaxError("Tax profile could not be saved. Check your permission and try again."); }
    finally { setTaxSaving(false); }
  }, [taxEditor, onChange, onSelect]);
  const moveActive = (direction: 1 | -1) => {
    if (visibleOptions.length === 0) return;
    setOpen(true);
    const next = activeIndex < 0 ? (direction === 1 ? 0 : visibleOptions.length - 1) : (activeIndex + direction + visibleOptions.length) % visibleOptions.length;
    setActiveIndex(next);
    scrollOptionIntoView(next);
  };

  const dropdown = open && !disabled && position && typeof document !== "undefined" ? createPortal(
    <div ref={dropdownRef} role="listbox" className="pointer-events-auto fixed z-[10000] max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-xl" style={{ left: position.left, top: position.top, width: position.width }}>
      {loading && visibleOptions.length === 0 ? <div className="px-3 py-2 text-xs text-slate-500">Loading items...</div> : loadError ? <div className="px-3 py-2 text-xs text-red-600">Unable to load items. Please try again.</div> : visibleOptions.length === 0 ? <div className="px-3 py-2 text-xs text-slate-500">No matching items.</div> : visibleOptions.map((product, index) => {
        const taxIncomplete = requireTaxReady && taxProfileIncomplete(product);
        return <button key={product.id} ref={(element) => { optionRefs.current[index] = element; }} type="button" role="option" aria-selected={index === activeIndex} className={`pointer-events-auto block w-full cursor-pointer border-b border-slate-100 px-3.5 py-2.5 text-left last:border-b-0 focus:outline-none ${taxIncomplete ? "bg-amber-50 text-slate-700 hover:bg-amber-100" : index === activeIndex || index === hoverIndex ? "bg-emerald-50" : "hover:bg-emerald-50"}`} onMouseEnter={() => { setActiveIndex(index); setHoverIndex(index); }} onMouseLeave={() => setHoverIndex(-1)} onPointerDown={(event) => { event.preventDefault(); event.stopPropagation(); selectProduct(product); }} onClick={(event) => { event.preventDefault(); event.stopPropagation(); selectProduct(product); }}>
          <div className="flex items-center justify-between gap-2 text-[13px] font-medium text-slate-800"><span>{labelFor(product)}</span>{taxIncomplete && <span className="rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">{canManageTax ? "Set PPN" : "Needs PPN"}</span>}</div>
        </button>;
      })}
    </div>, document.body) : null;

  const taxEditorModal = <Dialog open={Boolean(taxEditor)} onOpenChange={(openState) => { if (!openState && !taxSaving) setTaxEditor(null); }}>
    {taxEditor && <DialogContent className="max-w-md p-4">
      <div className="mb-3"><div className="text-sm font-semibold text-slate-900">Set PPN · {labelFor(taxEditor.product)}</div><div className="mt-1 text-xs text-slate-500">Update the item tax profile without leaving this transaction.</div></div>
      <div className="space-y-3">
        <label className="block text-xs font-medium text-slate-700">Tax Treatment<select className="mt-1 h-9 w-full rounded-md border border-slate-300 px-3 text-sm" value={taxEditor.category} onChange={(event) => setTaxEditor((current) => current ? { ...current, category: event.target.value as TaxEditorState["category"] } : current)}><option value="STANDARD">Standard PPN</option><option value="SPECIAL">Special PPN</option><option value="NON_VAT">Non VAT</option><option value="EXEMPT">Exempt</option></select></label>
        {(taxEditor.category === "STANDARD" || taxEditor.category === "SPECIAL") && <label className="block text-xs font-medium text-slate-700">PPN Rate (%)<input type="number" min="0.01" max="100" step="0.01" className="mt-1 h-9 w-full rounded-md border border-slate-300 px-3 text-sm" value={taxEditor.rate} onChange={(event) => setTaxEditor((current) => current ? { ...current, rate: Number(event.target.value) } : current)} /></label>}
        <label className="block text-xs font-medium text-slate-700">Tax Reason / Notes<input className="mt-1 h-9 w-full rounded-md border border-slate-300 px-3 text-sm" value={taxEditor.reason} onChange={(event) => setTaxEditor((current) => current ? { ...current, reason: event.target.value } : current)} /></label>
        <label className="block text-xs font-medium text-slate-700">Tax Reference<input className="mt-1 h-9 w-full rounded-md border border-slate-300 px-3 text-sm" value={taxEditor.reference} onChange={(event) => setTaxEditor((current) => current ? { ...current, reference: event.target.value } : current)} /></label>
        {taxError && <div className="text-xs font-medium text-red-600" role="alert">{taxError}</div>}
      </div>
      <div className="mt-4 flex justify-end gap-2"><button type="button" className="h-9 rounded-md border border-slate-300 px-4 text-sm" disabled={taxSaving} onClick={() => setTaxEditor(null)}>Cancel</button><button type="button" className="h-9 rounded-md bg-blue-600 px-4 text-sm font-medium text-white disabled:opacity-60" disabled={taxSaving} onClick={() => void saveTaxProfile()}>{taxSaving ? "Saving..." : "Save PPN"}</button></div>
    </DialogContent>}
  </Dialog>;

  return <div ref={rootRef} className="relative"><input ref={inputRef} type="text" value={query} disabled={disabled} placeholder={placeholder} autoComplete="off" role="combobox" aria-haspopup="listbox" aria-expanded={open} aria-autocomplete="list" data-form-control data-form-density="compact" className={`${FORM_UI.controlBase} ${FORM_UI.density.compact.control}`} onFocus={() => { updatePosition(); setOpen(true); }} onChange={(event) => { const next = event.target.value; setQuery(next); updatePosition(); setOpen(true); setActiveIndex(0); if (!next.trim() && value) onChange(0); }} onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); moveActive(1); return; } if (event.key === "ArrowUp") { event.preventDefault(); moveActive(-1); return; } if (event.key === "Home" && open && visibleOptions.length > 0) { event.preventDefault(); setActiveIndex(0); scrollOptionIntoView(0); return; } if (event.key === "End" && open && visibleOptions.length > 0) { event.preventDefault(); const endIndex = visibleOptions.length - 1; setActiveIndex(endIndex); scrollOptionIntoView(endIndex); return; } if (event.key === "Enter" && open && activeIndex >= 0 && visibleOptions[activeIndex]) { event.preventDefault(); selectProduct(visibleOptions[activeIndex]); return; } }} />{dropdown}{taxEditorModal}</div>;
}

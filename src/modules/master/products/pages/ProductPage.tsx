import { Printer } from "lucide-react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import SearchBox from "@/components/datatable/SearchBox";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import ProductTable from "../components/ProductTable";
import ProductForm from "../components/ProductForm";
import ProductDetailDialog from "../components/ProductDetailDialog";
import type { InventoryTreatment, ItemType, Product, TaxCategory } from "../types";
import { productApi } from "../api/productApi";
import { exportApi } from "../api/exportApi";
import { useProducts, useCreateProduct, useUpdateProduct } from "../hooks/useProducts";
import { useAuthStore } from "@/store/auth";
import { isSuperuser } from "@/lib/access";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";

const EXPORT_POLL_DELAYS_MS = [2000, 3000, 5000, 8000, 10000];
const EXPORT_BACKGROUND_POLL_DELAY_MS = 15000;
const EXPORT_POLL_TIMEOUT_MS = 5 * 60 * 1000;

export default function ProductPage() {
  const user = useAuthStore((state) => state.user);
  const canCreateProduct = isSuperuser(user);
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<Product | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("products-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [treatmentFilter, setTreatmentFilter] = useState<InventoryTreatment | "">("");
  const [itemTypeFilter, setItemTypeFilter] = useState<ItemType | "">("");
  const [taxFilter, setTaxFilter] = useState<TaxCategory | "">("");
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<"idle" | "starting" | "processing" | "failed">("idle");
  const [exportError, setExportError] = useState<string | null>(null);

  const query = useProducts({ page, page_size: pageSize, search: debouncedSearch || undefined, item_type: itemTypeFilter || undefined, inventory_treatment: treatmentFilter || undefined, tax_category: taxFilter || undefined });
  const classification = useQuery({
    queryKey: ["product-classification-master"],
    queryFn: async () => (await productApi.classificationMaster()).data,
  });
  const accountLookup = useQuery({ queryKey: ["product-page-account-lookup", "all-active-posting"], queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }) });
  const createMutation = useCreateProduct();
  const updateMutation = useUpdateProduct();
  const data = query.data ?? {};
  const rows: Product[] = data.items ?? [];
  const pages = Math.max(Number(data.total_pages ?? 0), 1);
  const total = Number(data.total_items ?? 0);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => setPage(1), [debouncedSearch, itemTypeFilter, treatmentFilter, taxFilter, pageSize]);

  useEffect(() => window.localStorage.setItem("products-page-size", String(pageSize)), [pageSize]);

  useEffect(() => {
    if (!query.isFetching && data.total_pages != null && page > pages) setPage(pages);
  }, [data.total_pages, page, pages, query.isFetching]);

  useEffect(() => {
    if (!exportJobId) return;

    let cancelled = false;
    let timer: number | undefined;
    let pollAttempt = 0;
    const startedAt = Date.now();

    const scheduleNextPoll = (poll: () => Promise<void>) => {
      if (cancelled) return;
      const foregroundDelay = EXPORT_POLL_DELAYS_MS[Math.min(pollAttempt, EXPORT_POLL_DELAYS_MS.length - 1)];
      const delay = document.visibilityState === "hidden"
        ? EXPORT_BACKGROUND_POLL_DELAY_MS
        : foregroundDelay;
      pollAttempt += 1;
      timer = window.setTimeout(poll, delay);
    };

    const poll = async () => {
      if (cancelled) return;

      if (Date.now() - startedAt >= EXPORT_POLL_TIMEOUT_MS) {
        setExportStatus("failed");
        setExportJobId(null);
        setExportError("Export is taking longer than expected. Please try again later.");
        return;
      }

      try {
        const response = await exportApi.getExport(exportJobId);
        const job = response.data;
        if (cancelled) return;

        if (job.status === "READY" && job.download_url) {
          setExportStatus("idle");
          setExportJobId(null);
          setExportError(null);
          window.location.assign(job.download_url);
          return;
        }

        if (job.status === "FAILED") {
          setExportStatus("failed");
          setExportJobId(null);
          setExportError(job.error_message || "Export failed");
          return;
        }

        setExportStatus("processing");
        scheduleNextPoll(poll);
      } catch (error: any) {
        if (cancelled) return;
        setExportStatus("failed");
        setExportJobId(null);
        setExportError(error?.response?.data?.detail || "Unable to check export status");
      }
    };

    scheduleNextPoll(poll);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [exportJobId]);

  const handleCreate = () => { setSelected(null); setFormOpen(true); };
  const handleEdit = (product: Product) => { setSelected(product); setFormOpen(true); };
  const handleSubmit = async (payload: any) => {
    if (selected) await updateMutation.mutateAsync({ id: selected.id, payload });
    else await createMutation.mutateAsync(payload);
    setFormOpen(false);
    setSelected(null);
  };

  const handleExport = async () => {
    setExportError(null);
    setExportStatus("starting");
    try {
      const response = await exportApi.createProductsExport();
      setExportJobId(response.data.job_id);
      setExportStatus("processing");
    } catch (error: any) {
      setExportStatus("failed");
      setExportError(error?.response?.data?.detail || "Unable to start export");
    }
  };

  const exportBusy = exportStatus === "starting" || exportStatus === "processing";
  const exportLabel = exportStatus === "starting"
    ? "Starting export..."
    : exportStatus === "processing"
      ? "Preparing XLS..."
      : "Download XLS";

  return <>
    <div className="space-y-6">
      <PageHeader
        title="Products"
        description="Product Master"
        actions={<div className="flex items-center gap-2">
          <Button onClick={handleExport} disabled={exportBusy}>{exportLabel}</Button>
          {canCreateProduct && <Button onClick={handleCreate}>New Product</Button>}
          <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</div>}
      />
      {exportError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {exportError}
        </div>
      )}
      <Card>
        <div className="mb-2 flex flex-wrap items-center gap-2"><div className="min-w-[250px] flex-1">          <SearchBox value={search} onChange={setSearch} placeholder="Search item code or name..." />
</div><Button type="button" size="sm" variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(value=>!value)}>Filters{[itemTypeFilter,treatmentFilter,taxFilter].filter(Boolean).length ? ` (${[itemTypeFilter,treatmentFilter,taxFilter].filter(Boolean).length})` : ""}</Button></div>
        {showFilters && <div className="mb-2 grid gap-2 border-t border-slate-100 pt-2 md:grid-cols-3">          <select className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" value={itemTypeFilter} onChange={(event) => setItemTypeFilter(event.target.value as ItemType | "")}>
            <option value="">Buy and sell</option><option value="BUY">Buy items</option><option value="SELL">Sell items</option>
          </select>
          <select className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" value={treatmentFilter} onChange={(event) => setTreatmentFilter(event.target.value as InventoryTreatment | "")}>
            <option value="">All treatments</option>
            <option value="REVIEW_REQUIRED">Treatment Review Required</option>
            <option value="STOCK">Stock / Warehouse</option>
            <option value="DIRECT_USE">Direct Use</option>
            <option value="FIXED_ASSET">Fixed Asset</option>
            <option value="NON_STOCK">Non-stock / Service</option>
          </select>
          <select className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" value={taxFilter} onChange={(event) => setTaxFilter(event.target.value as TaxCategory | "")}>
            <option value="">All tax profiles</option>
            <option value="REVIEW_REQUIRED">Tax Review Required</option>
            <option value="STANDARD">Standard PPN</option>
            <option value="EXEMPT">PPN Exempt</option>
            <option value="NON_TAXABLE">Non PPN</option>
            <option value="SPECIAL">Special Tax</option>
          </select>
</div>}
        {query.isLoading ? <Loading/> : <>
          <ProductTable rows={rows} accounts={accountLookup.data ?? []} onEdit={handleEdit} onView={(product) => setDetailId(product.id)}/>
          <div className="flex flex-wrap items-center justify-between gap-2"><label className="text-xs">Rows per page <select className="ml-1 rounded border border-slate-300 px-2 py-1" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1)}}><option value={50}>50</option><option value={100}>100</option></select></label><Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="products" onChange={setPage}/></div>
        </>}
      </Card>
    </div>
    <ProductForm open={formOpen} product={selected} groups={classification.data ?? []} loading={classification.isLoading || createMutation.isPending || updateMutation.isPending} onClose={() => { setFormOpen(false); setSelected(null); }} onSubmit={handleSubmit}/>
    <ProductDetailDialog productId={detailId} accounts={accountLookup.data ?? []} onClose={() => setDetailId(null)} onEdit={(product) => { setDetailId(null); handleEdit(product); }}/>
  </>;
}

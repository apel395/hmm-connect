import { Printer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import SearchBox from "@/components/datatable/SearchBox";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import ProductTable from "../components/ProductTable";
import ProductForm from "../components/ProductForm";
import type { Product } from "../types";
import { productApi } from "../api/productApi";
import { exportApi } from "../api/exportApi";
import { useProducts, useCreateProduct, useUpdateProduct } from "../hooks/useProducts";
import { useAuthStore } from "@/store/auth";
import { isSuperuser } from "@/lib/access";

const PAGE_SIZE = 25;
const EXPORT_POLL_DELAYS_MS = [2000, 3000, 5000, 8000, 10000];
const EXPORT_BACKGROUND_POLL_DELAY_MS = 15000;
const EXPORT_POLL_TIMEOUT_MS = 5 * 60 * 1000;

export default function ProductPage() {
  const user = useAuthStore((state) => state.user);
  const canCreateProduct = isSuperuser(user);
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<Product | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<"idle" | "starting" | "processing" | "failed">("idle");
  const [exportError, setExportError] = useState<string | null>(null);

  const query = useProducts({ page, page_size: PAGE_SIZE, search: debouncedSearch || undefined });
  const classification = useQuery({
    queryKey: ["product-classification-master"],
    queryFn: async () => (await productApi.classificationMaster()).data,
  });
  const createMutation = useCreateProduct();
  const updateMutation = useUpdateProduct();
  const data = query.data ?? {};
  const rows: Product[] = data.items ?? [];
  const pages = Math.max(Number(data.total_pages ?? 0), 1);
  const total = Number(data.total_items ?? 0);

  const classificationProducts = useMemo(() => (classification.data ?? []).flatMap((group) =>
    group.subgroups.map((subgroup) => ({
      group_code: group.code,
      group_name: group.name,
      subgroup_code: subgroup.code,
      subgroup_name: subgroup.name,
    } as Product)),
  ), [classification.data]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => setPage(1), [debouncedSearch]);

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
        <div className="mb-4 max-w-md">
          <SearchBox value={search} onChange={setSearch} placeholder="Search item code or name..." />
        </div>
        {query.isLoading ? <Loading/> : <>
          <ProductTable rows={rows} onEdit={handleEdit}/>
          <Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="products" onChange={setPage}/>
        </>}
      </Card>
    </div>
    <ProductForm open={formOpen} product={selected} products={classificationProducts} loading={classification.isLoading || createMutation.isPending || updateMutation.isPending} onClose={() => { setFormOpen(false); setSelected(null); }} onSubmit={handleSubmit}/>
  </>;
}

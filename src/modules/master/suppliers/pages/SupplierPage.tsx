import DataWorkspace from "@/components/workspace/DataWorkspace";
import { Printer } from "lucide-react";
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import SupplierDetail from "../components/SupplierDetail";
import SupplierForm from "../components/SupplierForm";
import SupplierTable from "../components/SupplierTable";
import type { Supplier, SupplierPayload } from "../types";
import { useAuthStore } from "@/store/auth";
import { hasPermission } from "@/lib/access";
import {
  useCreateSupplier,
  useDeleteSupplier,
  useSupplier,
  useSupplierPage,
  useUpdateSupplier,
} from "../hooks/useSuppliers";

type StatusFilter = "all" | "active" | "inactive";
interface ValidationDetail { loc?: Array<string | number>; msg?: string; }

function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "An unexpected error occurred. Please try again.";
  const status = error.response?.status;
  const payload = error.response?.data as { detail?: string | ValidationDetail[]; message?: string } | undefined;
  const detail = payload?.detail;
  if (Array.isArray(detail)) {
    const message = detail.map((item) => {
      const field = item.loc?.filter((part) => part !== "body").join(".");
      return [field, item.msg].filter(Boolean).join(": ");
    }).filter(Boolean).join("; ");
    if (message) return message;
  }
  if (typeof detail === "string") return detail;
  if (payload?.message) return payload.message;
  if (status === 400) return "The supplier information is invalid.";
  if (status === 404) return "Supplier not found.";
  if (status === 409) return "A supplier with this code or name already exists.";
  if (status === 422) return "Please check the supplier fields and try again.";
  if (status && status >= 500) return "The server could not process the request.";
  return "Unable to complete the supplier request.";
}

function supplierPayload(supplier: Supplier, isActive = supplier.is_active): SupplierPayload {
  return {
    code: supplier.code,
    name: supplier.name,
    address: supplier.address ?? "",
    bank_name: supplier.bank_name ?? "",
    bank_account_number: supplier.bank_account_number ?? "",
    bank_account_name: supplier.bank_account_name ?? "",
    is_pkp: supplier.is_pkp,
    npwp: supplier.npwp ?? "",
    nitku: supplier.nitku ?? "",
    tax_registration_name: supplier.tax_registration_name ?? "",
    is_active: isActive,
    payable_account_id: supplier.payable_account_id ?? null,
    rows: supplier.rows?.map((row) => ({ id: row.id, pic_name: row.pic_name, phone: row.phone, unit: row.unit, item: row.item })) ?? [],
  };
}

export default function SupplierPage() {
  const user = useAuthStore((state) => state.user);
  const canCreateSupplier = hasPermission(user, "finance.manage");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("suppliers-page-size")) === 100 ? 100 : 50);
  const suppliersQuery = useSupplierPage({
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    is_active: status === "all" ? undefined : status === "active",
  });
  const createMutation = useCreateSupplier();
  const updateMutation = useUpdateSupplier();
  const deleteMutation = useDeleteSupplier();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [viewId, setViewId] = useState<number>();
  const [formError, setFormError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<number | null>(null);
  const detailQuery = useSupplier(viewId);
  const result = suppliersQuery.data;
  const rows = result?.items ?? [];
  const pages = Math.max(result?.total_pages ?? 0, 1);
  const total = result?.total_items ?? 0;

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => setPage(1), [debouncedSearch, status, pageSize]);
  useEffect(() => window.localStorage.setItem("suppliers-page-size", String(pageSize)), [pageSize]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  function openCreate() { setEditing(null); setFormError(null); setFormOpen(true); }
  function openEdit(supplier: Supplier) { setEditing(supplier); setFormError(null); setFormOpen(true); }

  async function save(payload: SupplierPayload) {
    if (createMutation.isPending || updateMutation.isPending) return;
    setFormError(null);
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, payload });
        toast.success("Supplier updated successfully.");
      } else {
        await createMutation.mutateAsync(payload);
        toast.success("Supplier created successfully.");
      }
      setFormOpen(false); setEditing(null);
    } catch (error) { setFormError(errorMessage(error)); }
  }

  async function toggleStatus(supplier: Supplier) {
    const nextActive = !supplier.is_active;
    if (!window.confirm(`${nextActive ? "Activate" : "Deactivate"} supplier "${supplier.name}"?`)) return;
    setActionId(supplier.id);
    try {
      await updateMutation.mutateAsync({ id: supplier.id, payload: supplierPayload(supplier, nextActive) });
      toast.success(`Supplier ${nextActive ? "activated" : "deactivated"}.`);
    } catch (error) { toast.error(errorMessage(error)); }
    finally { setActionId(null); }
  }

  async function remove(supplier: Supplier) {
    if (!window.confirm(`Delete supplier "${supplier.name}"? This cannot be undone.`)) return;
    setActionId(supplier.id);
    try {
      await deleteMutation.mutateAsync(supplier.id);
      toast.success("Supplier deleted successfully.");
      if (viewId === supplier.id) setViewId(undefined);
    } catch (error) { toast.error(errorMessage(error)); }
    finally { setActionId(null); }
  }

  return <DataWorkspace area="Master data">
    <div className="workspace-body">
      <PageHeader title="Suppliers" description="Manage supplier profiles, contacts, banking details, and availability." actions={<>
{canCreateSupplier && <Button onClick={openCreate}>Add Supplier</Button>}
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}/>
      <Card className="workspace-data">
        <div className="mb-2 flex flex-col gap-2 sm:flex-row">
          <Input type="search" aria-label="Search suppliers" placeholder="Search supplier code or name..." value={search} className="sm:max-w-md" onChange={(event) => setSearch(event.target.value)}/>
          <select aria-label="Filter suppliers by status" value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option>
          </select>
        </div>
        {suppliersQuery.isLoading ? <div className="py-12"><Loading/></div> : suppliersQuery.isError ? <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center"><p className="text-sm text-red-700">{errorMessage(suppliersQuery.error)}</p><Button className="mt-4" size="sm" variant="outline" onClick={() => suppliersQuery.refetch()}>Try Again</Button></div> : <><SupplierTable rows={rows} busyId={actionId} onView={(supplier) => setViewId(supplier.id)} onEdit={openEdit} onToggle={toggleStatus} onDelete={remove}/><div className="flex flex-wrap items-center justify-between gap-2"><label className="text-xs">Rows per page <select className="ml-1 rounded border border-slate-300 px-2 py-1" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1)}}><option value={50}>50</option><option value={100}>100</option></select></label><Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="suppliers" onChange={setPage}/></div></>}
      </Card>
    </div>
    <SupplierForm open={formOpen} supplier={editing} loading={createMutation.isPending || (updateMutation.isPending && actionId === null)} error={formError} onClose={() => { if (createMutation.isPending || updateMutation.isPending) return; setFormOpen(false); setEditing(null); setFormError(null); }} onSubmit={save}/>
    <SupplierDetail open={viewId !== undefined} supplier={detailQuery.data} loading={detailQuery.isLoading} error={detailQuery.isError ? errorMessage(detailQuery.error) : null} onClose={() => setViewId(undefined)}/>
  </DataWorkspace>;
}

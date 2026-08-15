import { useMemo, useState } from "react";
import { Eye, FileSearch, Plus, Upload } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { exportCsv } from "@/utils/exportCsv";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import { attachmentApi } from "@/modules/document-attachments/attachmentApi";
import { parseAttachmentError } from "@/modules/document-attachments/attachmentUtils";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import PurchasingDocumentForm from "./PurchasingDocumentForm";
import {
  formatMoney,
  purchasingDocumentError,
} from "./documentUtils";
import type {
  PurchasingDocument,
  PurchasingDocumentFilters,
  PurchasingDocumentPayload,
} from "./types";
import {
  useCreatePurchasingDocument,
  usePurchasingDocument,
  usePurchasingDocuments,
  usePurchasingDocumentSummary,
  useUpdatePurchasingDocument,
} from "./usePurchasingDocuments";

function dateValue(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("id-ID");
}

export default function PurchasingDocumentsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [status, setStatus] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [cashflowStage, setCashflowStage] = useState("");
  const [documentDateFrom, setDocumentDateFrom] = useState("");
  const [documentDateTo, setDocumentDateTo] = useState("");
  const [expectedDateFrom, setExpectedDateFrom] = useState("");
  const [expectedDateTo, setExpectedDateTo] = useState("");
  const [active, setActive] = useState("true");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<PurchasingDocument | null>(null);
  const [viewId, setViewId] = useState<number>();
  const [formError, setFormError] = useState("");
  const [progress, setProgress] = useState(0);

  const filters = useMemo<PurchasingDocumentFilters>(
    () => ({
      page,
      page_size: 25,
      search: search.trim() || undefined,
      document_type: documentType || undefined,
      status: status.trim().toUpperCase() || undefined,
      source_type: sourceType || undefined,
      supplier_id: supplierId ? Number(supplierId) : undefined,
      cashflow_stage: cashflowStage || undefined,
      document_date_from: documentDateFrom || undefined,
      document_date_to: documentDateTo || undefined,
      expected_payment_date_from: expectedDateFrom || undefined,
      expected_payment_date_to: expectedDateTo || undefined,
      is_active: active === "all" ? undefined : active === "true",
    }),
    [
      active,
      cashflowStage,
      documentDateFrom,
      documentDateTo,
      documentType,
      expectedDateFrom,
      expectedDateTo,
      page,
      search,
      sourceType,
      status,
      supplierId,
    ],
  );
  const summaryFilters = useMemo(() => {
    const { page: _page, page_size: _pageSize, ...rest } = filters;
    return rest;
  }, [filters]);

  const documents = usePurchasingDocuments(filters);
  const summary = usePurchasingDocumentSummary(summaryFilters);
  const suppliers = useSuppliers();
  const detail = usePurchasingDocument(viewId);
  const createDocument = useCreatePurchasingDocument();
  const updateDocument = useUpdatePurchasingDocument();
  const saving = createDocument.isPending || updateDocument.isPending;

  function resetPage() {
    setPage(1);
  }

  function openCreate() {
    setEditing(null);
    setFormError("");
    setProgress(0);
    setFormOpen(true);
  }

  function _openEdit(document: PurchasingDocument) {
    setEditing(document);
    setFormError("");
    setProgress(0);
    setFormOpen(true);
  }

  async function submit(payload: PurchasingDocumentPayload, file: File | null) {
    if (saving) return;
    setFormError("");
    setProgress(0);
    try {
      if (editing) {
        await updateDocument.mutateAsync({ id: editing.id, payload });
        toast.success("Purchasing document updated.");
        setFormOpen(false);
        setEditing(null);
        return;
      }

      const response = await createDocument.mutateAsync(payload);
      const created = response.data;
      if (file) {
        try {
          await attachmentApi.upload(
            {
              entityType: "PURCHASING_DOCUMENT",
              entityId: created.id,
              file,
              attachmentType:
                created.document_type === "PURCHASE_REQUISITION"
                  ? "PR_DOCUMENT"
                  : "PO_DOCUMENT",
              documentNumber: created.document_number,
              documentDate: created.document_date,
              description: "Primary purchasing paper",
              sourceType:
                created.source_type === "LIVE" ? "LIVE" : "HISTORICAL_IMPORT",
            },
            setProgress,
          );
          toast.success("Purchasing document and attachment created.");
        } catch (attachmentError) {
          toast.warning(
            `Metadata was created, but the file was not uploaded: ${parseAttachmentError(attachmentError)}`,
          );
        }
      }
      setFormOpen(false);
      setViewId(created.id);
    } catch (error) {
      setFormError(purchasingDocumentError(error));
    }
  }

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          title="Purchasing Documents"
          description="Track uploaded Purchase Requisition and Purchase Order papers for audit and future reporting."
          actions={<div className="flex flex-wrap gap-2"><Button onClick={openCreate}><Plus className="h-4 w-4" /> Create</Button><Button variant="outline" onClick={openCreate}><Upload className="h-4 w-4" /> Import</Button><Button variant="outline" onClick={() => exportCsv("purchasing-documents.csv", ["Document Number","Type","Date","Supplier","Status","Attachments"], (documents.data?.items ?? []).map((item) => [item.document_number,item.document_type,item.document_date,item.supplier_name,item.status,item.attachment_count]))}>Export</Button></div>}
        />

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            [documents.data?.total ?? 0, "Documents Uploaded"],
            [summary.data?.missing_attachment_count ?? 0, "Missing Attachments"],
            ["—", "Expiring Contracts", "Future capability"],
            [documents.data?.items.length ?? 0, "Recent Activity", "Documents on this page"],
          ].map(([value, label, note]) => <Card key={label} className="p-5"><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold">{summary.isLoading ? "…" : value}</p>{note && <p className="mt-1 text-xs text-slate-500">{note}</p>}</Card>)}
        </div>

        <Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
            <Input
              type="search"
              placeholder="Search documents..."
              value={search}
              onChange={(event) => { setSearch(event.target.value); resetPage(); }}
            />
            <select value={documentType} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" onChange={(event) => { setDocumentType(event.target.value); resetPage(); }}>
              <option value="">All document types</option>
              <option value="PURCHASE_REQUISITION">Purchase Requisition</option>
              <option value="PURCHASE_ORDER">Purchase Order</option>
            </select>
            <Input placeholder="Status filter" value={status} onChange={(event) => { setStatus(event.target.value); resetPage(); }} />
            <select value={supplierId} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" onChange={(event) => { setSupplierId(event.target.value); resetPage(); }}>
              <option value="">All suppliers</option>
              {(suppliers.data ?? []).map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
            </select>
            <select value={cashflowStage} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" onChange={(event) => { setCashflowStage(event.target.value); resetPage(); }}>
              <option value="">All cash-flow stages</option>
              <option value="PLANNED">Planned</option>
              <option value="COMMITTED">Committed</option>
            </select>
            <select value={sourceType} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" onChange={(event) => { setSourceType(event.target.value); resetPage(); }}>
              <option value="">All sources</option>
              <option value="LIVE">Live</option>
              <option value="HISTORICAL_IMPORT">Historical Import</option>
              <option value="OPENING_BALANCE">Opening Balance</option>
              <option value="SYSTEM_GENERATED">System Generated</option>
            </select>
            <label className="text-xs text-slate-500">Document date from<Input type="date" value={documentDateFrom} onChange={(event) => { setDocumentDateFrom(event.target.value); resetPage(); }} /></label>
            <label className="text-xs text-slate-500">Document date to<Input type="date" value={documentDateTo} onChange={(event) => { setDocumentDateTo(event.target.value); resetPage(); }} /></label>
            <label className="text-xs text-slate-500">Expected date from<Input type="date" value={expectedDateFrom} onChange={(event) => { setExpectedDateFrom(event.target.value); resetPage(); }} /></label>
            <label className="text-xs text-slate-500">Expected date to<Input type="date" value={expectedDateTo} onChange={(event) => { setExpectedDateTo(event.target.value); resetPage(); }} /></label>
            <select value={active} className="h-10 self-end rounded-md border border-slate-300 bg-white px-3 text-sm" onChange={(event) => { setActive(event.target.value); resetPage(); }}>
              <option value="true">Active documents</option>
              <option value="false">Archived documents</option>
              <option value="all">All documents</option>
            </select>
          </div>
        </Card>

        <Card>
          {documents.isLoading ? (
            <div className="py-12"><Loading /></div>
          ) : documents.isError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <p className="text-sm text-red-700">{purchasingDocumentError(documents.error)}</p>
              <Button className="mt-3" variant="outline" size="sm" onClick={() => documents.refetch()}>Try Again</Button>
            </div>
          ) : (documents.data?.items.length ?? 0) === 0 ? (
            <div className="py-14 text-center">
              <FileSearch className="mx-auto mb-3 h-9 w-9 text-slate-400" />
              <p className="font-medium">No purchasing documents found.</p>
              <p className="mt-1 text-sm text-slate-500">Adjust the filters or upload a purchasing paper.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1450px] text-left text-sm">
                  <thead className="border-b text-xs uppercase text-slate-500">
                    <tr>
                      {["Document Number", "Document Type", "Document Date", "Supplier", "Department", "Total Amount", "Currency", "Cash-Flow Stage", "Expected Payment", "Status", "Source", "Attachments", "Actions"].map((heading) => (
                        <th key={heading} className="pb-3 pr-4 font-medium">{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {documents.data?.items.map((document) => (
                      <tr key={document.id} className="hover:bg-slate-50">
                        <td className="py-4 pr-4 font-semibold">{document.document_number}</td>
                        <td className="py-4 pr-4">{document.document_type.replaceAll("_", " ")}</td>
                        <td className="py-4 pr-4">{dateValue(document.document_date)}</td>
                        <td className="py-4 pr-4">{document.supplier_name || "—"}</td>
                        <td className="py-4 pr-4">{document.department_name || "—"}</td>
                        <td className="py-4 pr-4 font-medium">{formatMoney(document.total_amount, document.currency || "IDR")}</td>
                        <td className="py-4 pr-4">{document.currency || "—"}</td>
                        <td className="py-4 pr-4"><Badge variant={document.cashflow_stage === "PLANNED" ? "warning" : "info"}>{document.cashflow_stage}</Badge></td>
                        <td className="py-4 pr-4">{dateValue(document.expected_payment_date)}</td>
                        <td className="py-4 pr-4"><Badge variant="outline">{document.status}</Badge></td>
                        <td className="py-4 pr-4"><Badge variant={document.source_type === "HISTORICAL_IMPORT" ? "warning" : "secondary"}>{document.source_type.replaceAll("_", " ")}</Badge></td>
                        <td className="py-4 pr-4">{document.attachment_count}</td>
                        <td className="py-4">
                          <div className="flex min-w-max gap-2">
                            <Button size="xs" variant="outline" onClick={() => setViewId(document.id)}><Eye className="h-3.5 w-3.5" /> View</Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-5 flex items-center justify-between border-t pt-4 text-sm">
                <span className="text-slate-500">{documents.data?.total ?? 0} documents</span>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
                  <span>Page {page} of {documents.data?.total_pages || 1}</span>
                  <Button size="sm" variant="outline" disabled={page >= (documents.data?.total_pages || 1)} onClick={() => setPage((value) => value + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>

      <PurchasingDocumentForm
        open={formOpen}
        document={editing}
        suppliers={suppliers.data ?? []}
        saving={saving}
        progress={progress}
        error={formError}
        onClose={() => { setFormOpen(false); setEditing(null); setFormError(""); }}
        onSubmit={submit}
      />

      <Dialog open={viewId !== undefined} onOpenChange={(open) => !open && setViewId(undefined)}>
        <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
          <DialogHeader><DialogTitle>Purchasing Document Details</DialogTitle></DialogHeader>
          <DialogBody>
            {detail.isLoading ? (
              <Loading />
            ) : detail.isError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{purchasingDocumentError(detail.error)}</div>
            ) : detail.data ? (
              <div className="space-y-6">
                <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {[
                    ["Document Number", detail.data.document_number],
                    ["Document Type", detail.data.document_type.replaceAll("_", " ")],
                    ["Document Date", dateValue(detail.data.document_date)],
                    ["Source", detail.data.source_type.replaceAll("_", " ")],
                    ["Status", detail.data.status],
                    ["Supplier", detail.data.supplier_name],
                    ["Department", detail.data.department_name],
                    ["Location", detail.data.location_name],
                    ["Responsible User", detail.data.responsible_user_name],
                    ["Currency", detail.data.currency],
                    ["Subtotal", detail.data.subtotal && formatMoney(detail.data.subtotal, detail.data.currency || "IDR")],
                    ["Tax", detail.data.tax_amount && formatMoney(detail.data.tax_amount, detail.data.currency || "IDR")],
                    ["Total", detail.data.total_amount && formatMoney(detail.data.total_amount, detail.data.currency || "IDR")],
                    ["Cash-Flow Stage", detail.data.cashflow_stage],
                    ["Expected Payment", detail.data.expected_payment_date && dateValue(detail.data.expected_payment_date)],
                    ["External Reference", detail.data.external_reference],
                    ["Created", new Date(detail.data.created_at).toLocaleString("id-ID")],
                    ["Updated", new Date(detail.data.updated_at).toLocaleString("id-ID")],
                  ].filter((field) => field[1]).map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
                      <dd className="mt-1 whitespace-pre-wrap text-sm">{value}</dd>
                    </div>
                  ))}
                  {detail.data.notes && (
                    <div className="sm:col-span-2 lg:col-span-3">
                      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Notes</dt>
                      <dd className="mt-1 whitespace-pre-wrap text-sm">{detail.data.notes}</dd>
                    </div>
                  )}
                </dl>
                <DocumentAttachments
                  entityType="PURCHASING_DOCUMENT"
                  entityId={detail.data.id}
                  title="Purchasing Paper Attachments"
                />
              </div>
            ) : null}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewId(undefined)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

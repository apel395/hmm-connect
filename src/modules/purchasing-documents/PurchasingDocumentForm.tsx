import { useEffect, useRef, useState, type FormEvent } from "react";
import { FileText, Upload, X } from "lucide-react";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import type { Supplier } from "@/modules/master/suppliers/types";
import { formatFileSize } from "@/modules/document-attachments/attachmentUtils";
import { addDecimalStrings } from "./documentUtils";
import type {
  PurchasingDocument,
  PurchasingDocumentPayload,
  PurchasingDocumentSource,
  PurchasingDocumentType,
} from "./types";

const ACCEPTED_EXTENSIONS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".webp",
  ".doc", ".docx", ".xls", ".xlsx",
];
const MAX_FILE_SIZE = 10 * 1024 * 1024;

interface Props {
  open: boolean;
  document?: PurchasingDocument | null;
  suppliers: Supplier[];
  saving: boolean;
  progress: number;
  error?: string | null;
  onClose: () => void;
  onSubmit: (payload: PurchasingDocumentPayload, file: File | null) => void;
}

const initialForm = (): PurchasingDocumentPayload => ({
  document_type: "PURCHASE_REQUISITION",
  document_number: "",
  document_date: "",
  status: "",
  source_type: "HISTORICAL_IMPORT",
  supplier_id: null,
  currency: "IDR",
  subtotal: null,
  tax_amount: null,
  total_amount: null,
  cashflow_stage: "PLANNED",
  expected_payment_date: null,
  external_reference: null,
  notes: null,
});

export default function PurchasingDocumentForm({
  open,
  document,
  suppliers,
  saving,
  progress,
  error,
  onClose,
  onSubmit,
}: Props) {
  const [form, setForm] = useState<PurchasingDocumentPayload>(initialForm);
  const [file, setFile] = useState<File | null>(null);
  const [localError, setLocalError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const isEdit = Boolean(document);

  useEffect(() => {
    if (!open) return;
    setLocalError("");
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
    setForm(
      document
        ? {
            document_type: document.document_type,
            document_number: document.document_number,
            document_date: document.document_date,
            status: document.status,
            source_type:
              document.source_type === "LIVE" ? "LIVE" : "HISTORICAL_IMPORT",
            supplier_id: document.supplier_id,
            currency: document.currency,
            subtotal: document.subtotal,
            tax_amount: document.tax_amount,
            total_amount: document.total_amount,
            cashflow_stage:
              document.document_type === "PURCHASE_REQUISITION"
                ? "PLANNED"
                : "COMMITTED",
            expected_payment_date: document.expected_payment_date,
            external_reference: document.external_reference,
            notes: document.notes,
          }
        : initialForm(),
    );
  }, [document, open]);

  function update<K extends keyof PurchasingDocumentPayload>(
    field: K,
    value: PurchasingDocumentPayload[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function changeType(value: PurchasingDocumentType) {
    setForm((current) => ({
      ...current,
      document_type: value,
      cashflow_stage:
        value === "PURCHASE_REQUISITION" ? "PLANNED" : "COMMITTED",
    }));
  }

  function validateFile(selected: File): string | null {
    if (selected.size === 0) return "The selected file is empty.";
    if (selected.size > MAX_FILE_SIZE) return "The file exceeds the 10 MB limit.";
    const extension = `.${selected.name.split(".").pop()?.toLowerCase() ?? ""}`;
    return ACCEPTED_EXTENSIONS.includes(extension)
      ? null
      : "This file type is not supported.";
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    if (
      !form.document_number.trim() ||
      !form.document_date ||
      !form.status.trim()
    ) {
      setLocalError("Document number, document date, and status are required.");
      return;
    }
    if (!isEdit && !file) {
      setLocalError("Select the purchasing paper to upload.");
      return;
    }
    if (file) {
      const fileError = validateFile(file);
      if (fileError) {
        setLocalError(fileError);
        return;
      }
    }
    setLocalError("");
    const suggestedTotal =
      form.subtotal !== null && form.tax_amount !== null
        ? addDecimalStrings(form.subtotal, form.tax_amount)
        : "";
    onSubmit(
      {
        ...form,
        document_number: form.document_number.trim(),
        status: form.status.trim().toUpperCase(),
        currency: form.currency?.trim().toUpperCase() || null,
        total_amount: form.total_amount || suggestedTotal || null,
        external_reference: form.external_reference?.trim() || null,
        notes: form.notes?.trim() || null,
      },
      file,
    );
  }

  const suggestedTotal =
    form.subtotal !== null && form.tax_amount !== null
      ? addDecimalStrings(form.subtotal, form.tax_amount)
      : "";

  return (
    <Dialog open={open} onOpenChange={(value) => !value && !saving && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit Document Metadata" : "Upload Purchasing Document"}</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <div className="grid gap-5 sm:grid-cols-2">
              {(localError || error) && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 sm:col-span-2">
                  {localError || error}
                </div>
              )}
              <label className="space-y-1 text-sm font-medium">
                <span>Document Type *</span>
                <select
                  value={form.document_type}
                  disabled={saving}
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                  onChange={(event) => changeType(event.target.value as PurchasingDocumentType)}
                >
                  <option value="PURCHASE_REQUISITION">Purchase Requisition</option>
                  <option value="PURCHASE_ORDER">Purchase Order</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Document Number *</span>
                <Input value={form.document_number} disabled={saving} onChange={(event) => update("document_number", event.target.value)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Document Date *</span>
                <Input type="date" value={form.document_date} disabled={saving} onChange={(event) => update("document_date", event.target.value)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Status *</span>
                <Input placeholder="e.g. APPROVED" value={form.status} disabled={saving} onChange={(event) => update("status", event.target.value)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Source</span>
                <select
                  value={form.source_type}
                  disabled={saving}
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                  onChange={(event) => update("source_type", event.target.value as PurchasingDocumentSource)}
                >
                  <option value="HISTORICAL_IMPORT">Historical Paper</option>
                  <option value="LIVE">Current Operations</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Cash-Flow Stage</span>
                <Input value={form.cashflow_stage} disabled />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Supplier</span>
                <select
                  value={form.supplier_id ?? ""}
                  disabled={saving}
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                  onChange={(event) => update("supplier_id", event.target.value ? Number(event.target.value) : null)}
                >
                  <option value="">Not specified</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplier.code} — {supplier.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Expected Payment Date</span>
                <Input type="date" value={form.expected_payment_date ?? ""} disabled={saving} onChange={(event) => update("expected_payment_date", event.target.value || null)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Currency</span>
                <Input maxLength={3} value={form.currency ?? ""} disabled={saving} onChange={(event) => update("currency", event.target.value)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Subtotal</span>
                <Input inputMode="decimal" value={form.subtotal ?? ""} disabled={saving} onChange={(event) => update("subtotal", event.target.value || null)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Tax Amount</span>
                <Input inputMode="decimal" value={form.tax_amount ?? ""} disabled={saving} onChange={(event) => update("tax_amount", event.target.value || null)} />
              </label>
              <label className="space-y-1 text-sm font-medium">
                <span>Total Amount</span>
                <Input inputMode="decimal" placeholder={suggestedTotal ? `Suggested: ${suggestedTotal}` : ""} value={form.total_amount ?? ""} disabled={saving} onChange={(event) => update("total_amount", event.target.value || null)} />
              </label>
              <label className="space-y-1 text-sm font-medium sm:col-span-2">
                <span>External Reference</span>
                <Input value={form.external_reference ?? ""} disabled={saving} onChange={(event) => update("external_reference", event.target.value)} />
              </label>
              <label className="space-y-1 text-sm font-medium sm:col-span-2">
                <span>Notes</span>
                <textarea
                  rows={3}
                  value={form.notes ?? ""}
                  disabled={saving}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-[#086B5A] focus:outline-none focus:ring-2 focus:ring-[#086B5A]"
                  onChange={(event) => update("notes", event.target.value)}
                />
              </label>

              {!isEdit && (
                <div className="sm:col-span-2">
                  <div
                    className="rounded-xl border-2 border-dashed border-[#DCD6CB] bg-[#FAF8F4] p-6 text-center"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      const selected = event.dataTransfer.files[0] ?? null;
                      if (selected) {
                        setFile(selected);
                        setLocalError(validateFile(selected) ?? "");
                      }
                    }}
                  >
                    <input
                      ref={inputRef}
                      type="file"
                      className="hidden"
                      accept={ACCEPTED_EXTENSIONS.join(",")}
                      onChange={(event) => {
                        const selected = event.target.files?.[0] ?? null;
                        setFile(selected);
                        setLocalError(selected ? validateFile(selected) ?? "" : "");
                      }}
                    />
                    {file ? (
                      <div className="flex items-center justify-center gap-3">
                        <FileText className="h-7 w-7 text-[#086B5A]" />
                        <div className="max-w-md text-left">
                          <div className="truncate text-sm font-semibold" title={file.name}>{file.name}</div>
                          <div className="text-xs text-slate-500">{formatFileSize(file.size)}</div>
                        </div>
                        <Button type="button" size="xs" variant="ghost" onClick={() => {
                          setFile(null);
                          if (inputRef.current) inputRef.current.value = "";
                        }}>
                          <X className="h-4 w-4" /> Clear
                        </Button>
                      </div>
                    ) : (
                      <>
                        <Upload className="mx-auto mb-2 h-7 w-7 text-[#086B5A]" />
                        <p className="text-sm font-medium">Drop the purchasing paper here</p>
                        <p className="mt-1 text-xs text-slate-500">PDF, images, Word, or Excel · maximum 10 MB</p>
                        <Button type="button" className="mt-3" size="sm" variant="outline" onClick={() => inputRef.current?.click()}>
                          Browse File
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}
              {saving && progress > 0 && (
                <div className="sm:col-span-2">
                  <div className="mb-1 flex justify-between text-xs text-slate-500">
                    <span>Uploading attachment…</span><span>{progress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100">
                    <div className="h-2 rounded-full bg-[#086B5A]" style={{ width: `${progress}%` }} />
                  </div>
                </div>
              )}
            </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={saving} onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={saving}>{isEdit ? "Save Metadata" : "Create & Upload"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

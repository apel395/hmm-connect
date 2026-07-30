import { useRef, useState, type FormEvent } from "react";
import { Download, Eye, FileText, Paperclip, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
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
import { attachmentApi } from "./attachmentApi";
import {
  extractDownloadFilename,
  formatFileSize,
  isPreviewableMimeType,
  parseAttachmentError,
} from "./attachmentUtils";
import {
  useDeleteAttachment,
  useDocumentAttachments,
  useUploadAttachment,
} from "./useDocumentAttachments";
import type {
  AttachmentEntityType,
  AttachmentSourceType,
  DocumentAttachment,
} from "./types";

const DEFAULT_EXTENSIONS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".webp",
  ".doc", ".docx", ".xls", ".xlsx",
];
const ATTACHMENT_TYPES = [
  "SUPPORTING_DOCUMENT",
  "INVOICE",
  "QUOTATION",
  "DELIVERY_NOTE",
  "RECEIPT",
  "PAYMENT_PROOF",
  "CONTRACT",
  "OTHER",
];

interface Props {
  entityType: AttachmentEntityType;
  entityId: number;
  readOnly?: boolean;
  title?: string;
  allowedFileTypes?: string[];
  maxFileSize?: number;
}

export default function DocumentAttachments({
  entityType,
  entityId,
  readOnly = false,
  title = "Document Attachments",
  allowedFileTypes = DEFAULT_EXTENSIONS,
  maxFileSize = 10 * 1024 * 1024,
}: Props) {
  const attachments = useDocumentAttachments(entityType, entityId);
  const upload = useUploadAttachment(entityType, entityId);
  const remove = useDeleteAttachment(entityType, entityId);
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [attachmentType, setAttachmentType] = useState("SUPPORTING_DOCUMENT");
  const [documentNumber, setDocumentNumber] = useState("");
  const [documentDate, setDocumentDate] = useState("");
  const [description, setDescription] = useState("");
  const [sourceType, setSourceType] = useState<AttachmentSourceType>("LIVE");
  const [formError, setFormError] = useState("");
  const [progress, setProgress] = useState(0);
  const [actionId, setActionId] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function resetForm() {
    setFile(null);
    setAttachmentType("SUPPORTING_DOCUMENT");
    setDocumentNumber("");
    setDocumentDate("");
    setDescription("");
    setSourceType("LIVE");
    setFormError("");
    setProgress(0);
    if (fileInput.current) fileInput.current.value = "";
  }

  function validateFile(selected: File): string | null {
    if (selected.size === 0) return "The selected file is empty.";
    if (selected.size > maxFileSize) {
      return `The selected file exceeds the ${formatFileSize(maxFileSize)} limit.`;
    }
    const extension = `.${selected.name.split(".").pop()?.toLowerCase() ?? ""}`;
    const allowed = allowedFileTypes.some((type) => {
      const normalized = type.toLowerCase();
      return normalized.startsWith(".")
        ? normalized === extension
        : normalized === selected.type.toLowerCase();
    });
    return allowed ? null : "This file type is not supported.";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (upload.isPending) return;
    if (!file) {
      setFormError("Select a file to upload.");
      return;
    }
    const validationError = validateFile(file);
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setFormError("");
    try {
      await upload.mutateAsync({
        input: {
          entityType,
          entityId,
          file,
          attachmentType,
          documentNumber: documentNumber.trim() || undefined,
          documentDate: documentDate || undefined,
          description: description.trim() || undefined,
          sourceType,
        },
        onProgress: setProgress,
      });
      toast.success("Attachment uploaded successfully.");
      setOpen(false);
      resetForm();
    } catch (error) {
      setFormError(parseAttachmentError(error));
    }
  }

  async function getBlob(attachment: DocumentAttachment) {
    setActionId(attachment.id);
    try {
      return await attachmentApi.download(attachment.id);
    } catch (error) {
      toast.error(parseAttachmentError(error));
      return null;
    } finally {
      setActionId(null);
    }
  }

  async function download(attachment: DocumentAttachment) {
    const response = await getBlob(attachment);
    if (!response) return;
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = extractDownloadFilename(
      response.headers["content-disposition"],
      attachment.original_file_name,
    );
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function preview(attachment: DocumentAttachment) {
    const previewWindow = window.open("", "_blank", "noopener,noreferrer");
    const response = await getBlob(attachment);
    if (!response) {
      previewWindow?.close();
      return;
    }
    const url = URL.createObjectURL(response.data);
    if (previewWindow) previewWindow.location.href = url;
    else window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  async function deleteAttachment(attachment: DocumentAttachment) {
    if (!window.confirm(`Delete "${attachment.original_file_name}"?`)) return;
    setActionId(attachment.id);
    try {
      await remove.mutateAsync(attachment.id);
      toast.success("Attachment deleted.");
    } catch (error) {
      toast.error(parseAttachmentError(error));
    } finally {
      setActionId(null);
    }
  }

  if (entityId <= 0) {
    return (
      <Card>
        <h2 className="font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-slate-500">
          Save the document before adding attachments.
        </p>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 font-semibold">
              <Paperclip className="h-4 w-4 text-[#086B5A]" />
              {title}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Supporting files and historical documents for this record.
            </p>
          </div>
          {!readOnly && (
            <Button onClick={() => setOpen(true)}>
              <Upload className="h-4 w-4" />
              Upload
            </Button>
          )}
        </div>

        {attachments.isLoading ? (
          <div className="py-10"><Loading /></div>
        ) : attachments.isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-center">
            <p className="text-sm text-red-700">
              {parseAttachmentError(attachments.error)}
            </p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => attachments.refetch()}>
              Try Again
            </Button>
          </div>
        ) : (attachments.data ?? []).length === 0 ? (
          <div className="rounded-lg border border-dashed border-[#DCD6CB] py-10 text-center">
            <FileText className="mx-auto mb-2 h-8 w-8 text-slate-400" />
            <p className="text-sm font-medium">No attachments</p>
            <p className="mt-1 text-xs text-slate-500">
              Upload supporting documents for this record.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="pb-3 font-medium">File</th>
                  <th className="pb-3 font-medium">Type</th>
                  <th className="pb-3 font-medium">Document</th>
                  <th className="pb-3 font-medium">Description</th>
                  <th className="pb-3 font-medium">Uploaded</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(attachments.data ?? []).map((attachment) => (
                  <tr key={attachment.id}>
                    <td className="py-3 pr-4">
                      <div className="max-w-56 truncate font-medium" title={attachment.original_file_name}>
                        {attachment.original_file_name}
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatFileSize(attachment.file_size)} · {attachment.mime_type || "Unknown type"}
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <div>{attachment.attachment_type.replaceAll("_", " ")}</div>
                      {attachment.source_type === "HISTORICAL_IMPORT" && (
                        <Badge variant="warning" className="mt-1">Historical</Badge>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <div>{attachment.document_number || "—"}</div>
                      <div className="text-xs text-slate-500">{attachment.document_date || ""}</div>
                    </td>
                    <td className="max-w-56 truncate py-3 pr-4" title={attachment.description || undefined}>
                      {attachment.description || "—"}
                    </td>
                    <td className="py-3 pr-4">
                      <div>{new Date(attachment.uploaded_at).toLocaleDateString("id-ID")}</div>
                      {attachment.uploaded_by_id && (
                        <div className="text-xs text-slate-500">User #{attachment.uploaded_by_id}</div>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <Badge variant={attachment.is_active ? "success" : "secondary"}>
                        {attachment.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="py-3">
                      <div className="flex justify-end gap-2">
                        {isPreviewableMimeType(attachment.mime_type) && (
                          <Button
                            size="xs"
                            variant="outline"
                            disabled={actionId === attachment.id}
                            onClick={() => preview(attachment)}
                          >
                            <Eye className="h-3.5 w-3.5" /> Preview
                          </Button>
                        )}
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={actionId === attachment.id}
                          onClick={() => download(attachment)}
                        >
                          <Download className="h-3.5 w-3.5" /> Download
                        </Button>
                        {!readOnly && attachment.is_active && (
                          <Button
                            size="xs"
                            variant="danger"
                            loading={remove.isPending && actionId === attachment.id}
                            onClick={() => deleteAttachment(attachment)}
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Dialog open={open} onOpenChange={(value) => {
        if (!value && !upload.isPending) {
          setOpen(false);
          resetForm();
        }
      }}>
        <DialogContent className="max-w-2xl">
          <form onSubmit={submit}>
            <DialogHeader><DialogTitle>Upload Attachment</DialogTitle></DialogHeader>
            <DialogBody>
              <div className="grid gap-4 sm:grid-cols-2">
                {formError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 sm:col-span-2">
                    {formError}
                  </div>
                )}
                <label className="space-y-1 text-sm font-medium sm:col-span-2">
                  <span>File *</span>
                  <Input
                    ref={fileInput}
                    type="file"
                    accept={allowedFileTypes.join(",")}
                    disabled={upload.isPending}
                    onChange={(event) => {
                      const selected = event.target.files?.[0] ?? null;
                      setFile(selected);
                      setFormError(selected ? validateFile(selected) ?? "" : "");
                    }}
                  />
                  <span className="block text-xs font-normal text-slate-500">
                    PDF, images, Word, or Excel · maximum {formatFileSize(maxFileSize)}
                  </span>
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Attachment Type</span>
                  <select
                    value={attachmentType}
                    disabled={upload.isPending}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                    onChange={(event) => setAttachmentType(event.target.value)}
                  >
                    {ATTACHMENT_TYPES.map((type) => (
                      <option key={type} value={type}>{type.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Source</span>
                  <select
                    value={sourceType}
                    disabled={upload.isPending}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                    onChange={(event) => setSourceType(event.target.value as AttachmentSourceType)}
                  >
                    <option value="LIVE">Live</option>
                    <option value="HISTORICAL_IMPORT">Historical Import</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Document Number</span>
                  <Input value={documentNumber} disabled={upload.isPending} onChange={(event) => setDocumentNumber(event.target.value)} />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Document Date</span>
                  <Input type="date" value={documentDate} disabled={upload.isPending} onChange={(event) => setDocumentDate(event.target.value)} />
                </label>
                <label className="space-y-1 text-sm font-medium sm:col-span-2">
                  <span>Description</span>
                  <textarea
                    value={description}
                    disabled={upload.isPending}
                    rows={3}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-[#086B5A] focus:outline-none focus:ring-2 focus:ring-[#086B5A]"
                    onChange={(event) => setDescription(event.target.value)}
                  />
                </label>
                {upload.isPending && (
                  <div className="sm:col-span-2">
                    <div className="mb-1 flex justify-between text-xs text-slate-500">
                      <span>Uploading…</span><span>{progress}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full bg-[#086B5A] transition-all" style={{ width: `${progress}%` }} />
                    </div>
                  </div>
                )}
              </div>
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="outline" disabled={upload.isPending} onClick={() => {
                setOpen(false);
                resetForm();
              }}>
                Cancel
              </Button>
              <Button type="submit" loading={upload.isPending}>Upload Attachment</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

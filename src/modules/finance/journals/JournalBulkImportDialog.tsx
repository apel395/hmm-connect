import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, Upload } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import {
  confirmJournalImport,
  createJournalImport,
  downloadJournalImportCorrections,
  downloadJournalImportTemplate,
  getJournalImport,
  getJournalImportErrors,
  getJournalImportPreview,
  startJournalImport,
  uploadJournalImportFile,
} from "./api";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
};

const POLL_TERMINAL = new Set(["VALIDATED", "IMPORTED", "IMPORTED_WITH_ERRORS", "FAILED"]);
const IMPORT_DONE = new Set(["IMPORTED", "IMPORTED_WITH_ERRORS"]);
const WORKING = new Set(["QUEUED", "PROCESSING", "IMPORT_QUEUED", "IMPORTING"]);

// Session-scoped, per-user recovery; the API still verifies batch ownership.
const activeJobKey = () => {
  if (typeof window === "undefined") return "hmm-journal-import-job";
  try {
    const user = JSON.parse(window.localStorage.getItem("user") || "{}");
    return `hmm-journal-import-job-${user.id ?? user.user_id ?? user.username ?? "unknown"}`;
  } catch {
    return "hmm-journal-import-job-unknown";
  }
};

const savedJobId = (): number | undefined => {
  if (typeof window === "undefined") return undefined;
  const value = Number(window.sessionStorage.getItem(activeJobKey()));
  return Number.isSafeInteger(value) && value > 0 ? value : undefined;
};

const currency = new Intl.NumberFormat("id-ID", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export default function JournalBulkImportDialog({
  open,
  onOpenChange,
  onImported,
}: Props) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [batchName, setBatchName] = useState("Bulk Journal Import");
  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId] = useState<number | undefined>(savedJobId);

  const rememberJobId = (id: number | undefined) => {
    setJobId(id);
    if (id) window.sessionStorage.setItem(activeJobKey(), String(id));
    else window.sessionStorage.removeItem(activeJobKey());
  };
  const [action, setAction] = useState<"upload" | "resume" | "draft" | "post" | "correction" | null>(null);

  const job = useQuery({
    queryKey: ["journal-import", jobId],
    queryFn: () => getJournalImport(jobId!),
    enabled: open && Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && POLL_TERMINAL.has(status) ? false : 2000;
    },
  });

  const status = job.data?.status;
  const hasPreview = Boolean(jobId && status && ["VALIDATED", "IMPORTED", "IMPORTED_WITH_ERRORS"].includes(status));
  const preview = useQuery({
    queryKey: ["journal-import-preview", jobId, status],
    queryFn: () => getJournalImportPreview(jobId!),
    enabled: open && hasPreview,
  });
  const errors = useQuery({
    queryKey: ["journal-import-errors", jobId, status],
    queryFn: () => getJournalImportErrors(jobId!),
    enabled: open && Boolean(jobId) && Boolean(status && ["VALIDATED", "IMPORTED_WITH_ERRORS", "FAILED"].includes(status)),
  });

  useEffect(() => {
    if (status && IMPORT_DONE.has(status)) onImported();
  }, [status, onImported]);

  const validJournals = useMemo(
    () => preview.data?.journals.filter((row) => row.status === "VALID") ?? [],
    [preview.data],
  );
  const rejectedJournals = useMemo(
    () => preview.data?.journals.filter((row) => row.status === "ERROR") ?? [],
    [preview.data],
  );

  const busy = Boolean(action) || Boolean(status && WORKING.has(status));

  const reset = () => {
    setFile(null);
    setBatchName("Bulk Journal Import");
    setResumeId("");
    rememberJobId(undefined);
    setAction(null);
  };

  const close = () => {
    if (busy) return;
    // Closing must not discard a created batch. Reopening resumes its job ID.
    onOpenChange(false);
  };

  const resumeExisting = async () => {
    const id = Number(resumeId);
    if (!Number.isSafeInteger(id) || id <= 0) return toast.error("Enter a valid batch ID.");
    try {
      setAction("resume");
      const existing = await getJournalImport(id); // verifies current user's ownership
      queryClient.setQueryData(["journal-import", id], existing);
      rememberJobId(id);
      toast.success(`Resumed journal import batch #${id}.`);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Cannot access this batch.");
    } finally {
      setAction(null);
    }
  };

  const start = async () => {
    if (!jobId && !batchName.trim()) return toast.error("Enter an import name.");
    if (!file && (!jobId || status === "DRAFT")) return toast.error("Select an XLSX or CSV file.");
    try {
      setAction("upload");
      const id = jobId ?? (await createJournalImport(batchName.trim())).id;
      if (!jobId) rememberJobId(id); // Persist before any S3 request or /start.
      const currentStatus = jobId ? (await getJournalImport(id)).status : "DRAFT";
      if (currentStatus === "DRAFT") {
        if (!file) throw new Error("Re-select the file to resume this batch.");
        await uploadJournalImportFile(id, file);
      } else if (currentStatus !== "UPLOADED") {
        toast.info("This batch has already advanced. Its current status is being loaded.");
        await job.refetch();
        return;
      }
      const queued = await startJournalImport(id);
      queryClient.setQueryData(["journal-import", id], queued);
      if (jobId) await job.refetch();
      toast.success("File uploaded. Validation is queued on EC2.");
    } catch (error: any) {
      // The existing ID survives a timeout; never create a second batch on retry.
      if (jobId) await job.refetch().catch(() => undefined);
      toast.error(error?.response?.data?.detail || error?.message || "Import request failed. Reopen this batch or retry without creating a new one.");
    } finally {
      setAction(null);
    }
  };

  const confirm = async (postValid: boolean) => {
    if (!jobId) return;
    if (postValid && !window.confirm(
      `Post ${validJournals.length} valid journal(s) now? This will create General Ledger entries and apply accounting-period controls.`,
    )) return;
    try {
      setAction(postValid ? "post" : "draft");
      await confirmJournalImport(jobId, postValid);
      await job.refetch();
      toast.success(postValid ? "Valid journals are being imported and posted." : "Valid journals are being imported as Draft.");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Import could not start.");
    } finally {
      setAction(null);
    }
  };

  const startNew = () => {
    if (busy) return;
    if (jobId && status === "VALIDATED" && !window.confirm(
      `Start a different import? Batch #${jobId} will remain VALIDATED in the database.`,
    )) return;
    reset();
  };

  const downloadCorrections = async () => {
    if (!jobId) return;
    try {
      setAction("correction");
      await downloadJournalImportCorrections(jobId);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Correction file could not be downloaded.");
    } finally {
      setAction(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && (next ? onOpenChange(true) : close())}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Easy Bulk Journal Import</DialogTitle>
        </DialogHeader>

        <DialogBody className="space-y-5">
          {!jobId ? (
            <>
              <UploadStep
                file={file}
                batchName={batchName}
                setFile={setFile}
                setBatchName={setBatchName}
              />
              <div className="flex flex-wrap items-end gap-3 rounded-lg border p-3">
                <label className="text-sm font-medium">
                  Resume Existing Batch
                  <input
                    type="number"
                    min={1}
                    className="mt-1 block h-10 w-48 rounded border px-3"
                    placeholder="e.g. 153"
                    value={resumeId}
                    onChange={(event) => setResumeId(event.target.value)}
                  />
                </label>
                <Button variant="outline" loading={action === "resume"} onClick={resumeExisting}>
                  Resume Batch
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
                <span>Saved import batch <strong>#{jobId}</strong> · This batch can be resumed after closing or refreshing.</span>
                {!busy && <Button variant="outline" onClick={startNew}>Start New Import</Button>}
              </div>
              {job.isError && <Info>Could not load batch #{jobId}. Check your connection or start a new import.</Info>}
              {status === "DRAFT" && (
                <>
                  <Info>This batch has not finished uploading. Select the file again to retry using the same batch ID.</Info>
                  <UploadStep file={file} batchName={batchName} setFile={setFile} setBatchName={setBatchName} />
                </>
              )}
              {status === "UPLOADED" && <Info>Upload is complete. Start validation using this saved batch.</Info>}
              <div className="grid gap-3 sm:grid-cols-5">
                <Metric label="Status" value={statusLabel(status)} />
                <Metric label="Journals" value={job.data?.total_documents ?? 0} />
                <Metric label="Valid" value={status === "VALIDATED" ? job.data?.success_count ?? 0 : validJournals.length} tone="good" />
                <Metric label="Rejected" value={job.data?.failed_count ?? 0} tone={job.data?.failed_count ? "bad" : undefined} />
                <Metric label="Rows" value={job.data?.total_rows ?? 0} />
              </div>

              {status && ["QUEUED", "PROCESSING"].includes(status) && (
                <Info>Validating the file. No journal is created during this step.</Info>
              )}
              {status && ["IMPORT_QUEUED", "IMPORTING"].includes(status) && (
                <Info>Importing each valid journal independently. Rejected journals remain available for correction.</Info>
              )}
              {status === "FAILED" && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                  <div className="font-semibold">The worker could not complete this batch.</div>
                  <div className="mt-1">{job.data?.worker_error_message || "Unexpected worker failure."}</div>
                </div>
              )}
              {status === "VALIDATED" && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
                  Validation is complete. Review the journal totals below before importing.
                </div>
              )}
              {status && IMPORT_DONE.has(status) && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                  Imported {job.data?.success_count ?? 0} journal(s) and {job.data?.imported_rows ?? 0} line(s).
                  {status === "IMPORTED_WITH_ERRORS" ? " Rejected journals were not created." : ""}
                </div>
              )}

              {preview.data?.journals.length ? (
                <div className="overflow-hidden rounded-lg border">
                  <div className="max-h-80 overflow-auto">
                    <table className="w-full min-w-[760px] text-sm">
                      <thead className="sticky top-0 bg-slate-100 text-left text-xs uppercase text-slate-600">
                        <tr>
                          <th className="px-3 py-2">Document Number</th>
                          <th className="px-3 py-2">Date / Description</th>
                          <th className="px-3 py-2">Lines</th>
                          <th className="px-3 py-2 text-right">Debit</th>
                          <th className="px-3 py-2 text-right">Credit</th>
                          <th className="px-3 py-2 text-right">Difference</th>
                          <th className="px-3 py-2">Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.data.journals.map((row, index) => (
                          <tr key={`${row.journal_group}-${index}`} className="border-t align-top">
                            <td className="px-3 py-2 font-medium">{row.document_number || row.journal_group}</td>
                            <td className="px-3 py-2">
                              <div>{row.posting_date || "—"}</div>
                              <div className="max-w-xs truncate text-xs text-slate-500">{row.description || row.location || "—"}</div>
                            </td>
                            <td className="px-3 py-2">{row.line_count}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{currency.format(Number(row.debit))}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{currency.format(Number(row.credit))}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{currency.format(Number(row.difference))}</td>
                            <td className="px-3 py-2">
                              {row.status === "VALID" ? (
                                <span className="inline-flex items-center gap-1 text-emerald-700"><CheckCircle2 size={15} /> Ready</span>
                              ) : (
                                <div className="text-red-700">
                                  <span className="inline-flex items-center gap-1 font-medium"><AlertTriangle size={15} /> Needs correction</span>
                                  {row.errors.slice(0, 2).map((message) => <div key={message} className="mt-1 max-w-sm text-xs">{message}</div>)}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              {errors.data?.rows.length ? (
                <div className="text-sm text-slate-600">
                  {rejectedJournals.length || job.data?.failed_count || 0} journal(s) need correction. Downloading the correction file keeps only the rejected rows and their messages.
                </div>
              ) : null}
            </>
          )}
        </DialogBody>

        <DialogFooter>
          {!jobId ? (
            <>
              <Button variant="outline" onClick={close} disabled={busy}>Cancel</Button>
              <Button variant="outline" onClick={() => downloadJournalImportTemplate()} disabled={busy}>
                <Download size={16} /> Easy Template
              </Button>
              <Button onClick={start} loading={action === "upload"} disabled={!file}>
                <Upload size={16} /> Upload & Validate
              </Button>
            </>
          ) : status === "DRAFT" || status === "UPLOADED" ? (
            <>
              <Button variant="outline" onClick={close} disabled={busy}>Close</Button>
              <Button onClick={start} loading={action === "upload"} disabled={status === "DRAFT" && !file}>
                <Upload size={16} /> {status === "DRAFT" ? "Retry Upload & Validate" : "Start Validation"}
              </Button>
            </>
          ) : status === "VALIDATED" ? (
            <>
              <Button variant="outline" onClick={close} disabled={busy}>Close</Button>
              {errors.data?.rows.length ? (
                <Button variant="outline" onClick={downloadCorrections} loading={action === "correction"}>
                  <Download size={16} /> Correction File
                </Button>
              ) : null}
              <Button variant="secondary" onClick={() => confirm(false)} loading={action === "draft"} disabled={!validJournals.length}>
                Import Valid as Draft
              </Button>
              <Button onClick={() => confirm(true)} loading={action === "post"} disabled={!validJournals.length}>
                Import & Post Valid
              </Button>
            </>
          ) : (
            <>
              {errors.data?.rows.length ? (
                <Button variant="outline" onClick={downloadCorrections} loading={action === "correction"}>
                  <Download size={16} /> Correction File
                </Button>
              ) : null}
              <Button onClick={close} disabled={busy}>{busy ? "Processing..." : "Close"}</Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function UploadStep({
  file,
  batchName,
  setFile,
  setBatchName,
}: {
  file: File | null;
  batchName: string;
  setFile: (file: File | null) => void;
  setBatchName: (value: string) => void;
}) {
  return (
    <>
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
        <div className="font-semibold">Simple journal blocks</div>
        <div className="mt-1">Use the same fields as Create Journal Entry. Document Number identifies each journal; blank header cells continue the preceding document. Department is selected independently on each line. ERP generates one official journal number for the entire document.</div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm font-medium">
          Import Name
          <input className="mt-1 h-10 w-full rounded border px-3" value={batchName} onChange={(event) => setBatchName(event.target.value)} placeholder="January 2026 adjustments" />
        </label>
        <label className="text-sm font-medium">
          File
          <input className="mt-1 block w-full rounded border px-3 py-2 text-sm" type="file" accept=".xlsx,.csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
      </div>
      {file ? <div className="rounded border p-3 text-sm"><strong>{file.name}</strong> · {(file.size / 1024 / 1024).toFixed(2)} MB</div> : null}
      <div className="grid gap-3 text-sm md:grid-cols-3">
        <Rule title="1. Upload">The file is validated without creating journals.</Rule>
        <Rule title="2. Review">See each journal’s debit, credit, difference and errors.</Rule>
        <Rule title="3. Import">Import valid journals as Draft or explicitly Post them.</Rule>
      </div>
    </>
  );
}

function Rule({ title, children }: { title: string; children: ReactNode }) {
  return <div className="rounded border p-3"><div className="font-semibold">{title}</div><div className="mt-1 text-slate-600">{children}</div></div>;
}

function Info({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">{children}</div>;
}

function Metric({ label, value, tone }: { label: string; value: string | number; tone?: "good" | "bad" }) {
  const valueColor = tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-red-700" : "text-slate-900";
  return <div className="rounded border bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className={`mt-1 font-semibold ${valueColor}`}>{value}</div></div>;
}

function statusLabel(status?: string) {
  const labels: Record<string, string> = {
    DRAFT: "Upload incomplete",
    UPLOADED: "Uploaded",
    QUEUED: "Queued",
    PROCESSING: "Validating",
    VALIDATED: "Ready to import",
    IMPORT_QUEUED: "Import queued",
    IMPORTING: "Importing",
    IMPORTED: "Imported",
    IMPORTED_WITH_ERRORS: "Partially imported",
    FAILED: "Worker failed",
  };
  return status ? labels[status] || status : "—";
}

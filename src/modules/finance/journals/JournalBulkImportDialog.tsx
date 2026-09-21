import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Upload } from "lucide-react";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import {
  downloadJournalImportTemplate,
  getJournalImport,
  getJournalImportErrors,
  uploadJournalImport,
} from "./api";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
};

const TERMINAL = new Set(["IMPORTED", "FAILED"]);

export default function JournalBulkImportDialog({
  open,
  onOpenChange,
  onImported,
}: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [batchName, setBatchName] = useState("Bulk Journal Import");
  const [jobId, setJobId] = useState<number>();
  const [uploading, setUploading] = useState(false);

  const job = useQuery({
    queryKey: ["journal-import", jobId],
    queryFn: () => getJournalImport(jobId!),
    enabled: open && Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL.has(status) ? false : 2000;
    },
  });

  const errors = useQuery({
    queryKey: ["journal-import-errors", jobId],
    queryFn: () => getJournalImportErrors(jobId!),
    enabled: open && Boolean(jobId) && job.data?.status === "FAILED",
  });

  useEffect(() => {
    if (job.data?.status === "IMPORTED") {
      onImported();
    }
  }, [job.data?.status, onImported]);

  const reset = () => {
    setFile(null);
    setBatchName("Bulk Journal Import");
    setJobId(undefined);
    setUploading(false);
  };

  const close = () => {
    if (uploading) return;
    reset();
    onOpenChange(false);
  };

  const start = async () => {
    if (!file) {
      toast.error("Select an XLSX or CSV file.");
      return;
    }
    if (!batchName.trim()) {
      toast.error("Enter an import name.");
      return;
    }

    try {
      setUploading(true);
      const result = await uploadJournalImport(file, batchName.trim());
      setJobId(result.id);
      toast.success("Journal import queued on the EC2 worker.");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Journal import failed to start.");
    } finally {
      setUploading(false);
    }
  };

  const status = job.data?.status;
  const busy = uploading || Boolean(status && !TERMINAL.has(status));

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && (next ? onOpenChange(true) : close())}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import Bulk Journal</DialogTitle>
        </DialogHeader>

        <DialogBody className="space-y-5">
          {!jobId ? (
            <>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                Upload one XLSX or CSV file. <strong>document_number is optional</strong>; leave it blank
                and ERP will generate it automatically. Consecutive blank rows belong to the same journal.
                The EC2 worker validates the entire file before creating any journal.
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium">
                  Import Name
                  <input
                    className="mt-1 h-10 w-full rounded border px-3"
                    value={batchName}
                    onChange={(event) => setBatchName(event.target.value)}
                    placeholder="Salary August 2026"
                  />
                </label>

                <label className="text-sm font-medium">
                  File
                  <input
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                    type="file"
                    accept=".xlsx,.csv"
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  />
                </label>
              </div>

              {file && (
                <div className="rounded border p-3 text-sm">
                  <strong>{file.name}</strong> · {(file.size / 1024 / 1024).toFixed(2)} MB
                </div>
              )}

              <div className="rounded border p-4 text-sm">
                <div className="mb-2 font-semibold">Import rules</div>
                <ul className="list-disc space-y-1 pl-5 text-slate-600">
                  <li>Every journal must balance debit = credit.</li>
                  <li>Account, business unit and location codes must exist.</li>
                  <li>Document number is optional. Leave it blank for automatic ERP numbering.</li>
                  <li>If supplied, repeat the same document number for every line of that journal.</li>
                  <li>Existing journal document numbers are rejected.</li>
                  <li>Status DRAFT keeps the journal unposted; POSTED posts it to GL.</li>
                  <li>Maximum 5,000 rows / 500 journals per import.</li>
                </ul>
              </div>
            </>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Status" value={status || "—"} />
                <Metric label="Rows" value={job.data?.total_rows ?? 0} />
                <Metric label="Journals" value={job.data?.total_documents ?? 0} />
                <Metric label="Imported" value={job.data?.imported_rows ?? 0} />
              </div>

              {status === "FAILED" && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                  <div className="font-semibold">Import failed</div>
                  <div className="mt-1">{job.data?.worker_error_message || "Validation failed."}</div>
                </div>
              )}

              {status === "IMPORTED" && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                  Imported {job.data?.success_count ?? 0} journal(s) and {job.data?.imported_rows ?? 0} row(s).
                </div>
              )}

              {status === "PROCESSING" || status === "QUEUED" ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                  The file is being processed by the EC2 worker. This window will update automatically.
                </div>
              ) : null}

              {errors.data?.rows?.length ? (
                <div className="max-h-72 overflow-y-auto rounded border">
                  {errors.data.rows.map((row) => (
                    <div key={`${row.row_number}-${row.document_number}`} className="border-b p-3 text-sm last:border-b-0">
                      <div className="font-medium">
                        Row {row.row_number} · {row.document_number || "No document number"}
                      </div>
                      {row.errors.map((message) => (
                        <div key={message} className="mt-1 text-red-700">{message}</div>
                      ))}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </DialogBody>

        <DialogFooter>
          {!jobId ? (
            <>
              <Button variant="outline" onClick={close} disabled={uploading}>Cancel</Button>
              <Button variant="outline" onClick={() => downloadJournalImportTemplate()} disabled={uploading}>
                <Download size={16} /> Template
              </Button>
              <Button onClick={start} loading={uploading} disabled={!file}>
                <Upload size={16} /> Upload & Import
              </Button>
            </>
          ) : (
            <Button onClick={close} disabled={busy}>
              {status === "IMPORTED" || status === "FAILED" ? "Close" : "Processing..."}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  );
}

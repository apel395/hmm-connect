import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/interceptor";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/Dialog";

type StageBatch = {
  id: number;
  batch_number: string;
  status: string;
  total_rows: number;
  error_rows: number;
  warning_rows: number;
  imported_rows: number;
  message: string;
};
type StageSummary = StageBatch & {
  totals: { gross: string; receipt: string; aging: string };
  locations: Record<string, { invoices: number; gross: string; receipt: string; aging: string }>;
  issues: Record<string, number>;
  posting_enabled: boolean;
  reason: string;
};
type StagedRow = {
  row_number: number;
  invoice_number: string;
  status: string;
  data: {
    location_name?: string;
    invoice_date?: string | null;
    gross?: string;
    receipt?: string;
    aging?: string;
  };
  errors: string[];
  warnings: string[];
};
type RowPage = {
  items: StagedRow[];
  page: number;
  total: number;
  page_size: number;
};
const currency = (value: string | number | undefined) =>
  "Rp " + Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });

export default function ARImportStagingDialog({
  open, onOpenChange,
}: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [resumeId, setResumeId] = useState("");
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<"ALL" | "ERROR" | "REVIEW">("ALL");
  const [uploading, setUploading] = useState(false);

  const summary = useQuery({
    queryKey: ["ar-import-staging-summary", batchId],
    queryFn: async () => (await api.get<StageSummary>(`/ar-imports/${batchId}/summary`)).data,
    enabled: open && Boolean(batchId),
  });
  const rows = useQuery({
    queryKey: ["ar-import-staging-rows", batchId, page, filter],
    queryFn: async () => (await api.get<RowPage>(`/ar-imports/${batchId}/rows`, {
      params: { page, page_size: 30, status: filter === "ALL" ? undefined : filter },
    })).data,
    enabled: open && Boolean(batchId),
  });

  const upload = async () => {
    if (!file) return toast.error("Choose the Catering revenue recap .xlsx file");
    if (!file.name.toLowerCase().endsWith(".xlsx")) return toast.error("Only .xlsx files are supported");
    if (file.size > 5 * 1024 * 1024) return toast.error("Maximum upload size is 5 MB");
    try {
      setUploading(true);
      const payload = new FormData();
      payload.append("file", file);
      const result = (await api.post<StageBatch>("/ar-imports/stage", payload, {
        headers: { "Content-Type": undefined },
        timeout: 90_000,
      })).data;
      setBatchId(result.id);
      setResumeId(String(result.id));
      setPage(1);
      setFilter("ALL");
      setFile(null);
      toast.success(`Excel staged as batch #${result.id}. No AR or GL was posted.`);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Excel staging failed; no AR or GL was changed");
    } finally {
      setUploading(false);
    }
  };
  const resume = () => {
    const id = Number(resumeId);
    if (!Number.isSafeInteger(id) || id <= 0) return toast.error("Enter a valid staged batch ID");
    setBatchId(id);
    setPage(1);
    setFilter("ALL");
  };
  const close = () => { if (!uploading) onOpenChange(false); };
  const data = summary.data;
  const totalPages = Math.max(1, Math.ceil((rows.data?.total ?? 0) / 30));

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) close(); else onOpenChange(true); }}>
      <DialogContent className="max-w-6xl">
        <DialogHeader><DialogTitle>Catering AR Invoice Excel — Staging</DialogTitle></DialogHeader>
        <DialogBody className="max-h-[75vh] space-y-4 overflow-y-auto">
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            Review-only upload: creates a saved staging batch, not an AR invoice.
            No sales revenue, customer receipt, payment, journal, or GL posting occurs.
            Customer, due date and bank/tax evidence must be reconciled first.
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-52 flex-1 text-sm">
              2026 Project Catering recap (.xlsx)
              <input type="file" accept=".xlsx" disabled={uploading}
                className="mt-1 block w-full rounded-lg border border-slate-300 p-2 text-sm"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </label>
            <Button type="button" disabled={uploading || !file} loading={uploading}
              onClick={upload}>Stage Excel</Button>
          </div>
          <div className="flex flex-wrap items-end gap-2 border-t pt-3">
            <label className="text-sm">
              Resume staging batch
              <input type="number" min={1} value={resumeId} onChange={(e) => setResumeId(e.target.value)}
                placeholder="Batch ID" className="mt-1 block w-36 rounded-lg border p-2 text-sm" />
            </label>
            <Button type="button" variant="outline" disabled={uploading} onClick={resume}>Open Batch</Button>
          </div>
          {batchId && (
            <>
              {summary.isLoading && <div className="text-sm text-slate-500">Loading batch #{batchId}…</div>}
              {summary.isError && <div className="text-sm text-red-700">Batch #{batchId} is not accessible to this user.</div>}
              {data && (
                <>
                  <div className="text-sm font-medium">Batch #{data.id} · {data.status} · {data.total_rows} invoices</div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <div className="rounded border p-3 text-sm"><div className="text-slate-500">Total A/R source</div><strong>{currency(data.totals.gross)}</strong></div>
                    <div className="rounded border p-3 text-sm"><div className="text-slate-500">Receipts source</div><strong>{currency(data.totals.receipt)}</strong></div>
                    <div className="rounded border p-3 text-sm"><div className="text-slate-500">Aging source</div><strong>{currency(data.totals.aging)}</strong></div>
                  </div>
                  <div className="text-xs text-slate-600">
                    {data.error_rows} invoice(s) with blocking data issues; {data.warning_rows} with review warnings.
                    These staged values are not yet part of the Accounts Receivable balance.
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {Object.entries(data.locations).map(([site, location]) => (
                      <div key={site} className="rounded border px-3 py-2">
                        <strong>{site}</strong> · {location.invoices} invoices · {currency(location.gross)}
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <label htmlFor="ar-import-filter">Show</label>
                    <select id="ar-import-filter" value={filter}
                      className="rounded border px-2 py-1"
                      onChange={(e) => { setPage(1); setFilter(e.target.value as typeof filter); }}>
                      <option value="ALL">All invoices</option>
                      <option value="ERROR">Blocking errors</option>
                      <option value="REVIEW">Review items</option>
                    </select>
                  </div>
                  <div className="overflow-x-auto rounded border">
                    <table className="w-full min-w-[850px] text-left text-xs">
                      <thead className="bg-slate-100">
                        <tr>
                          {["Excel Row", "Invoice", "Location", "Date", "Gross", "Receipt", "Status & findings"].map((col) => (
                            <th key={col} className="px-2 py-2">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.data?.items.map((r) => (
                          <tr key={r.row_number} className="border-t align-top">
                            <td className="px-2 py-2">{r.row_number}</td>
                            <td className="max-w-44 break-words px-2 py-2 font-medium">{r.invoice_number}</td>
                            <td className="px-2 py-2">{r.data.location_name}</td>
                            <td className="px-2 py-2">{r.data.invoice_date ?? "MISSING"}</td>
                            <td className="whitespace-nowrap px-2 py-2">{currency(r.data.gross)}</td>
                            <td className="whitespace-nowrap px-2 py-2">{currency(r.data.receipt)}</td>
                            <td className="max-w-96 px-2 py-2">
                              <strong className={r.status === "ERROR" ? "text-red-700" : "text-amber-700"}>{r.status}</strong>
                              {r.errors.map((message) => <p key={message} className="mt-1 text-red-700">{message}</p>)}
                              {r.warnings.slice(0, 4).map((message) => <p key={message} className="mt-1 text-slate-600">{message}</p>)}
                              {r.warnings.length > 4 && <p className="mt-1 text-slate-500">+{r.warnings.length - 4} more review notes</p>}
                            </td>
                          </tr>
                        ))}
                        {rows.data && rows.data.items.length === 0 && <tr><td colSpan={7} className="p-4 text-center">No matching invoice rows</td></tr>}
                      </tbody>
                    </table>
                  </div>
                  {rows.data && totalPages > 1 && (
                    <div className="flex items-center justify-end gap-2 text-xs">
                      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                      Page {page} / {totalPages}
                      <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
                    </div>
                  )}
                  <p className="text-xs text-slate-600">{data.reason}</p>
                </>
              )}
            </>
          )}
        </DialogBody>
        <DialogFooter><Button type="button" variant="outline" disabled={uploading} onClick={close}>Close</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

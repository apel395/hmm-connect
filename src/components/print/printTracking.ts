import api from "@/api/client";

export type PrintAction = "PRINT_DIALOG" | "PDF_DOWNLOAD";
export type PrintTarget = { kind: string; id: number; revision?: string | null };
export type PrintStamp = {
  print_count: number; pdf_download_count: number; reprint_number: number;
  revision_number: number; revision_hash?: string; requested_at?: string; actor_name?: string;
  channel: PrintAction; physical_print_confirmed: false;
};
export type PrintWindow = Window & {
  mmhPreparePrint?: () => Promise<void>;
  mmhDownloadPdf?: () => Promise<void>;
};

export function createPrintSession(target: PrintTarget, snapshotHash?: string) {
  const pending: Partial<Record<PrintAction, string>> = {};
  const inflight: Partial<Record<PrintAction, Promise<PrintStamp>>> = {};
  return {
    issue(action: PrintAction): Promise<PrintStamp> {
      if (inflight[action]) return inflight[action]!;
      const requestId = pending[action] ?? crypto.randomUUID();
      pending[action] = requestId;
      const request = api.post<PrintStamp>(`/document-events/${target.kind}/${target.id}/print`, {
        request_id: requestId, action, expected_revision: target.revision || undefined, snapshot_hash: snapshotHash,
      }).then(response => { delete pending[action]; return response.data; })
        .finally(() => { delete inflight[action]; });
      inflight[action] = request;
      return request;
    },
  };
}

export async function printSnapshot(value: string) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function stampText(stamp: PrintStamp) {
  const number = stamp.channel === "PDF_DOWNLOAD" ? `PDF download #${stamp.pdf_download_count}` : `Print attempt #${stamp.print_count}`;
  const who = [stamp.actor_name, stamp.requested_at ? new Date(stamp.requested_at).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" }) + " WIB" : ""].filter(Boolean).join(" · ");
  return `${number}${stamp.channel === "PRINT_DIALOG" && stamp.reprint_number > 0 ? " · REPRINT" : ""} · Rev ${stamp.revision_number}${who ? ` · ${who}` : ""}`;
}

/** afterprint fires even when the dialog is cancelled; never mark it printed. */
export function attachNativePrintTracking(target: Window, prepare: () => Promise<void>, onError: () => void, shouldTrack = () => true) {
  let prepared = false;
  const before = () => { if (!prepared && shouldTrack()) { prepared = true; void prepare().catch(onError); } };
  const after = () => { prepared = false; };
  const key = (event: KeyboardEvent) => {
    if (shouldTrack() && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "p") {
      event.preventDefault();
      if (prepared) return;
      prepared = true;
      void prepare().then(() => target.print()).catch(() => { prepared = false; onError(); });
    }
  };
  target.addEventListener("beforeprint", before);
  target.addEventListener("afterprint", after);
  target.addEventListener("keydown", key);
  return {
    prepared: () => { prepared = true; },
    dispose: () => { target.removeEventListener("beforeprint", before); target.removeEventListener("afterprint", after); target.removeEventListener("keydown", key); },
  };
}

import { useCallback, useEffect, useRef, useState } from "react";
import { Printer } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import { attachNativePrintTracking, createPrintSession, printSnapshot, stampText } from "./printTracking";

export default function PurchasingPagePrintButton({ kind }: { kind: string }) {
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const session = useRef<{ hash: string; issue: ReturnType<typeof createPrintSession> } | undefined>(undefined);
  const native = useRef<ReturnType<typeof attachNativePrintTracking> | undefined>(undefined);
  const stampElement = useRef<HTMLDivElement | undefined>(undefined);
  const prepare = useCallback(async () => {
    const root = document.querySelector("main") ?? document.body;
    const copy = root.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("[data-print-stamp]").forEach(element => element.remove());
    const hash = await printSnapshot(copy.textContent ?? "");
    if (session.current?.hash !== hash) session.current = { hash, issue: createPrintSession({ kind, id: 0 }, hash) };
    const stamp = await session.current.issue.issue("PRINT_DIALOG");
    if (!stampElement.current) {
      stampElement.current = document.createElement("div");
      stampElement.current.dataset.printStamp = "true";
      stampElement.current.className = "hidden print:block text-xs";
      document.body.prepend(stampElement.current);
    }
    stampElement.current.textContent = stampText(stamp);
  }, [kind]);
  useEffect(() => {
    native.current = attachNativePrintTracking(window, prepare, () => toast.error("Print attempt could not be recorded"),
      () => document.activeElement?.tagName !== "IFRAME");
    return () => { native.current?.dispose(); stampElement.current?.remove(); };
  }, [prepare]);
  const print = async () => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await prepare(); native.current?.prepared(); window.print(); }
    catch { toast.error("Unable to record print attempt. Try again."); }
    finally { busyRef.current = false; setBusy(false); }
  };
  return <Button variant="outline" title="Print" aria-label="Print purchasing report" disabled={busy} onClick={print}><Printer size={16} /><span className="sr-only">Print</span></Button>;
}

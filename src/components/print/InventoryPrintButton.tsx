import { attachNativePrintTracking, createPrintSession, printSnapshot, stampText } from "./printTracking";
import { useEffect, useRef, useState } from "react";
import { Printer } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import useAuth from "@/store/auth";
import {
  renderInventoryPrint,
  type InventoryPrintReport,
} from "@/utils/inventoryPrint";

export default function InventoryPrintButton({
  loadReport,
  disabled,
  reportLabel = "Inventory",
  compact = false,
}: {
  loadReport: () => Promise<InventoryPrintReport>;
  disabled?: boolean;
  reportLabel?: string;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [printing,setPrinting]=useState(false);
  const tracking=useRef<ReturnType<typeof createPrintSession> | undefined>(undefined);
  const native=useRef<ReturnType<typeof attachNativePrintTracking> | undefined>(undefined);
  const printingRef=useRef(false);
  const [html, setHtml] = useState("");
  const [ready, setReady] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);
  useEffect(()=>()=>native.current?.dispose(),[]);
  const user = useAuth((state) => state.user);
  const prepare = async () => {
    setBusy(true);
    setReady(false);
    try {
      const report=await loadReport();
      const documentHtml=renderInventoryPrint(report,user?.full_name||user?.username||"User");
      tracking.current=report.printTracking?createPrintSession(report.printTracking,await printSnapshot(documentHtml)):undefined;
      setHtml(documentHtml);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Unable to prepare inventory report",
      );
    } finally {
      setBusy(false);
    }
  };
  const prepareTrackedPrint=async()=>{
    if(!tracking.current)return;
    const stamp=await tracking.current.issue("PRINT_DIALOG");
    const doc=frame.current?.contentDocument;
    if(doc){let node=doc.querySelector<HTMLElement>("[data-print-stamp]");if(!node){node=doc.createElement("div");node.dataset.printStamp="true";node.style.fontSize="9px";doc.body.prepend(node);}node.textContent=stampText(stamp);}
  };
  const print = async () => {
    const target = frame.current?.contentWindow;
    if (!ready || !target || printingRef.current) return;
    printingRef.current=true;setPrinting(true);
    try {await target.document.fonts.ready;await prepareTrackedPrint();native.current?.prepared();target.focus();target.print();}
    catch {toast.error("Unable to record print attempt. Try again.");}
    finally {printingRef.current=false;setPrinting(false);}
  };
  return (
    <>
      <Button
        variant="outline"
        size={compact ? "xs" : undefined}
        title="Print complete report"
        aria-label={`Print complete ${reportLabel.toLowerCase()} report`}
        disabled={disabled}
        loading={busy}
        onClick={prepare}
      >
        <Printer size={16} /><span className="sr-only">Print</span>
      </Button>
      <Dialog
        open={Boolean(html)}
        onOpenChange={(open) => {
          if (!open) {
            native.current?.dispose();setHtml("");
            setReady(false);
          }
        }}
      >
        <DialogContent className="max-w-6xl">
          <DialogHeader>
            <DialogTitle>{reportLabel} print preview</DialogTitle>
          </DialogHeader>
          <DialogBody className="bg-slate-100 p-3">
            <iframe
              ref={frame}
              srcDoc={html}
              sandbox="allow-same-origin allow-modals"
              title={`Complete filtered ${reportLabel.toLowerCase()} report`}
              onLoad={() => {setReady(true);native.current?.dispose();const target=frame.current?.contentWindow;if(target&&tracking.current)native.current=attachNativePrintTracking(target,prepareTrackedPrint,()=>toast.error("Print attempt could not be recorded"));}}
              className="h-[72vh] w-full border bg-white"
            />
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHtml("")}>
              Close
            </Button>
            <Button disabled={!ready||printing} onClick={print}>
              <Printer size={16} /><span className="sr-only">Print</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

import { useRef, useState } from "react";
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
}: {
  loadReport: () => Promise<InventoryPrintReport>;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [html, setHtml] = useState("");
  const [ready, setReady] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);
  const user = useAuth((state) => state.user);
  const prepare = async () => {
    setBusy(true);
    setReady(false);
    try {
      setHtml(
        renderInventoryPrint(
          await loadReport(),
          user?.full_name || user?.username || "User",
        ),
      );
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
  const print = async () => {
    const target = frame.current?.contentWindow;
    if (!ready || !target) return;
    await target.document.fonts.ready;
    target.focus();
    target.print();
  };
  return (
    <>
      <Button
        variant="outline"
        title="Print complete report"
        aria-label="Print complete inventory report"
        disabled={disabled}
        loading={busy}
        onClick={prepare}
      >
        <Printer size={16} /> Print
      </Button>
      <Dialog
        open={Boolean(html)}
        onOpenChange={(open) => {
          if (!open) {
            setHtml("");
            setReady(false);
          }
        }}
      >
        <DialogContent className="max-w-6xl">
          <DialogHeader>
            <DialogTitle>Inventory print preview</DialogTitle>
          </DialogHeader>
          <DialogBody className="bg-slate-100 p-3">
            <iframe
              ref={frame}
              srcDoc={html}
              sandbox="allow-same-origin allow-modals"
              title="Complete filtered inventory report"
              onLoad={() => setReady(true)}
              className="h-[72vh] w-full border bg-white"
            />
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHtml("")}>
              Close
            </Button>
            <Button disabled={!ready} onClick={print}>
              <Printer size={16} /> Print
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

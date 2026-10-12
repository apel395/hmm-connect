import { useRef, useState } from "react";
import { toast } from "sonner";
import { Printer } from "lucide-react";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";

interface PrintPreviewButtonProps {
  src: string;
  title: string;
  ariaLabel?: string;
  label?: string;
}

export default function PrintPreviewButton({ src, title, ariaLabel = "Print preview", label }: PrintPreviewButtonProps) {
  const [open, setOpen] = useState(false);
  const [frameLoaded, setFrameLoaded] = useState(false);
  const frameRef = useRef<HTMLIFrameElement>(null);

  const [printing,setPrinting]=useState(false);
  const print = async () => {
    if (!frameLoaded || frameRef.current?.contentDocument?.querySelector('[data-print-ready="false"]')) { toast.error("Wait for the report to load before printing"); return; }
    setPrinting(true);
    try {
      const target=frameRef.current?.contentWindow as (Window & {mmhPreparePrint?:()=>Promise<void>})|undefined;
      await target?.mmhPreparePrint?.();
      target?.focus();
      target?.print();
    } catch {
      toast.error("Unable to issue a tracked print copy. Try again.");
    } finally {setPrinting(false);}

  };

  return (
    <>
      <Button variant="outline" title="Print preview" aria-label={ariaLabel} onClick={() => { setFrameLoaded(false); setOpen(true); }}>
        <Printer size={18} />{label ? <span>{label}</span> : null}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-6xl">
          <DialogHeader>
            <DialogTitle className="font-semibold">{title}</DialogTitle>
          </DialogHeader>
          <DialogBody className="bg-slate-100 p-3">
            <iframe
              ref={frameRef}
              onLoad={() => setFrameLoaded(true)}
              src={src}
              title={title}
              className="h-[72vh] w-full rounded-lg border border-slate-200 bg-white"
            />
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
            <Button disabled={!frameLoaded || printing} onClick={print}><Printer size={16} /> Print</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

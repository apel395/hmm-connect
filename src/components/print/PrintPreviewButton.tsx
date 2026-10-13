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
  layouts?: { label: string; src: string; title: string }[];
}

export default function PrintPreviewButton({ src, title, ariaLabel = "Print preview", label, layouts }: PrintPreviewButtonProps) {
  const [open, setOpen] = useState(false);
  const [layoutIndex, setLayoutIndex] = useState(0);
  const selected = layouts?.[layoutIndex];
  const previewSrc = selected?.src ?? src;
  const previewTitle = selected?.title ?? title;
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
            <div className="flex flex-wrap items-center gap-3">
              <DialogTitle className="font-semibold">{previewTitle}</DialogTitle>
              {layouts && layouts.length > 1 && <label className="flex items-center gap-2 text-xs">Layout
                <select aria-label="Print layout" className="h-8 rounded border bg-white px-2" value={layoutIndex}
                  disabled={printing} onChange={event => { setFrameLoaded(false); setLayoutIndex(Number(event.target.value)); }}>
                  {layouts.map((layout, index) => <option key={layout.label} value={index}>{layout.label}</option>)}
                </select>
              </label>}
            </div>
          </DialogHeader>
          <DialogBody className="bg-slate-100 p-3">
            <iframe
              ref={frameRef}
              key={previewSrc}
              onLoad={() => setFrameLoaded(true)}
              src={previewSrc}
              title={previewTitle}
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

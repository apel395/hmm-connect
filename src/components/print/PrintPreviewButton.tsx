import { useRef, useState } from "react";
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
  const frameRef = useRef<HTMLIFrameElement>(null);

  const print = () => {
    frameRef.current?.contentWindow?.focus();
    frameRef.current?.contentWindow?.print();
  };

  return (
    <>
      <Button variant="outline" title="Print preview" aria-label={ariaLabel} onClick={() => setOpen(true)}>
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
              src={src}
              title={title}
              className="h-[72vh] w-full rounded-lg border border-slate-200 bg-white"
            />
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
            <Button onClick={print}><Printer size={16} /> Print</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

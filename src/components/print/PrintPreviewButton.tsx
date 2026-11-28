import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Download, Printer } from "lucide-react";
import type { PrintWindow } from "./printTracking";
import { exportTablesToExcel, printExcelFileName } from "@/utils/exportPrintTables";
import Button from "@/components/ui/Button";
import { ReportScopeNote } from "@/components/common/ReportActions";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";

interface PrintPreviewButtonProps {
  src: string;
  title: string;
  ariaLabel?: string;
  label?: string;
  note?: string;
  layouts?: { label: string; src: string; title: string }[];
}

export default function PrintPreviewButton({ src, title, ariaLabel = "Print preview", label, note, layouts }: PrintPreviewButtonProps) {
  const [open, setOpen] = useState(false);
  const queryClient=useQueryClient();
  const [layoutIndex, setLayoutIndex] = useState(0);
  const selected = layouts?.[layoutIndex];
  const previewSrc = selected?.src ?? src;
  const previewTitle = selected?.title ?? title;
  const [frameLoaded, setFrameLoaded] = useState(false);
  const frameRef = useRef<HTMLIFrameElement>(null);

  const [printing,setPrinting]=useState(false);
  const printingRef=useRef(false);
  const purchasing=/\/(purchase-requisitions|market-lists|purchase-orders|receiving|goods-receipts)\/\d+\/print/.test(previewSrc);
  const print = async () => {
    if (!frameLoaded || frameRef.current?.contentDocument?.querySelector('[data-print-ready="false"]')) { toast.error("Wait for the report to load before printing"); return; }
    if(printingRef.current)return;
    printingRef.current=true;setPrinting(true);
    try {
      const target=frameRef.current?.contentWindow as (Window & {mmhPreparePrint?:()=>Promise<void>})|undefined;
      await target?.mmhPreparePrint?.();
      target?.focus();
      target?.print();
    } catch {
      toast.error("Unable to issue a tracked print copy. Try again.");
    } finally {printingRef.current=false;setPrinting(false);}

  };

  const setPreviewOpen=(value:boolean)=>{
    setOpen(value);
    if(value||!purchasing)return;
    const match=previewSrc.match(/\/(purchase-requisitions|market-lists|purchase-orders|receiving|goods-receipts)\/(\d+)\/print/);
    if(match){const keys:Record<string,string>={"purchase-requisitions":"purchase-requisition","market-lists":"market-list","purchase-orders":"purchase-order","receiving":"goods-receipt","goods-receipts":"goods-receipt"};void queryClient.invalidateQueries({queryKey:[keys[match[1]],Number(match[2])]});}
  };
  const downloadPdf=async()=>{
    const target=frameRef.current?.contentWindow as PrintWindow|undefined;
    if(!frameLoaded||printingRef.current||target?.document.querySelector('[data-print-ready="false"]'))return;
    if(!target?.mmhDownloadPdf){toast.error("Wait for the document to load");return;}
    printingRef.current=true;setPrinting(true);
    try {await target.mmhDownloadPdf();}catch {toast.error("Unable to download PDF. Refresh the preview and try again.");}
    finally {printingRef.current=false;setPrinting(false);}
  };
  const downloadExcel=async()=>{
    const doc=frameRef.current?.contentDocument;
    if(!frameLoaded||!doc||printingRef.current||doc.querySelector('[data-print-ready="false"]')){toast.error("Wait for the report to load before exporting");return;}
    try {await exportTablesToExcel(doc, printExcelFileName(previewTitle));}
    catch {toast.error("Unable to export the report to Excel");}
  };
  return (
    <>
      <Button variant="outline" title="Print preview" aria-label={ariaLabel} onClick={() => { setFrameLoaded(false); setOpen(true); }}>
        <Printer size={18} />{label ? <span>{label}</span> : null}
      </Button>
      <Dialog open={open} onOpenChange={setPreviewOpen}>
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
            {note && <ReportScopeNote className="mb-2">{note}</ReportScopeNote>}
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
            <Button variant="outline" onClick={() => setPreviewOpen(false)}>Close</Button>
            <Button variant="outline" disabled={!frameLoaded||printing} onClick={() => void downloadExcel()} aria-label="Export print preview to Excel"><Download size={16} /> Excel</Button>
            {purchasing&&<Button variant="outline" disabled={!frameLoaded||printing} onClick={downloadPdf}>Download PDF</Button>}
            <Button disabled={!frameLoaded || printing} onClick={print}><Printer size={16} /> Print</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

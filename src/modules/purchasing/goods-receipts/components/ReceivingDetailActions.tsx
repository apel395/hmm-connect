import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Ellipsis, FileCheck2, FilePlus2, Pencil, PencilLine, RotateCcw, XCircle } from "lucide-react";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";

export type ReceivingPrimaryAction = {
  label: string;
  onClick: () => void;
  loading?: boolean;
  icon?: "invoice" | "prepare";
};

export type ReceivingMenuAction = {
  label: string;
  onSelect: () => void;
  kind: "edit" | "depost" | "cost" | "reject" | "return";
};

const menuIcons = {
  edit: Pencil,
  depost: PencilLine,
  cost: PencilLine,
  reject: XCircle,
  return: RotateCcw,
};

export default function ReceivingDetailActions({
  receiptId,
  receiptNumber,
  canPrint,
  primary,
  menuActions,
}: {
  receiptId: number;
  receiptNumber: string;
  canPrint: boolean;
  primary?: ReceivingPrimaryAction;
  menuActions: ReceivingMenuAction[];
}) {
  const PrimaryIcon = primary?.icon === "invoice" ? FileCheck2 : primary?.icon === "prepare" ? FilePlus2 : null;
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 print:hidden">
      {primary && (
        <Button size="lg" className="min-h-10 rounded-lg px-4 shadow-sm" loading={primary.loading}
          onClick={primary.onClick}>
          {PrimaryIcon && <PrimaryIcon size={17} aria-hidden="true" />}
          {primary.label}
        </Button>
      )}
      {canPrint && (
        <div className="[&_button]:h-10 [&_button]:w-10 [&_button]:rounded-lg [&_button]:px-0">
          <PrintPreviewButton src={"/receiving/" + receiptId + "/print"}
            title={"Receiving " + receiptNumber} ariaLabel={"Print Receiving " + receiptNumber} />
        </div>
      )}
      {menuActions.length > 0 && (
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button variant="outline" size="lg" className="min-h-10 rounded-lg px-3"
              aria-label="More Receiving actions">
              <Ellipsis size={19} aria-hidden="true" />
              <span className="hidden sm:inline">More</span>
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content sideOffset={8} align="end"
              className="z-[80] min-w-52 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl outline-none">
              {menuActions.map(action => {
                const Icon = menuIcons[action.kind];
                const dangerous = action.kind === "return" || action.kind === "reject";
                return (
                  <DropdownMenu.Item key={action.kind}
                    onSelect={action.onSelect}
                    className={"flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2.5 text-sm outline-none transition-colors focus:bg-slate-100 data-[highlighted]:bg-slate-100 " +
                      (dangerous ? "text-red-700" : "text-slate-700")}>
                    <Icon size={16} aria-hidden="true" />
                    {action.label}
                  </DropdownMenu.Item>
                );
              })}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      )}
    </div>
  );
}

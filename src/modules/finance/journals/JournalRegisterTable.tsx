import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import { Link } from "react-router-dom";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { journalAccountingLabel } from "./journalState";
import { sourceDocumentPath } from "./sourceDocument";
import type { Journal } from "./api";

type JournalRow = Journal;

interface JournalRegisterTableProps {
  rows: JournalRow[];
  loading: boolean;
  error: boolean;
  selectedIds: number[];
  allPageSelected: boolean;
  onTogglePage: () => void;
  onToggleRow: (id: number) => void;
  onView: (id: number) => void;
  onCopy: (id: number) => void;
  onPost: (id: number) => void;
  onUnpost: (id: number) => void;
  onVoidPayment: (row: JournalRow) => void;
  actionPending: boolean;
}

const amount = (value: number) => Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const menuItem = "flex cursor-pointer items-center rounded px-3 py-2 text-xs text-slate-700 outline-none data-[highlighted]:bg-slate-100 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40";

export default function JournalRegisterTable({
  rows, loading, error, selectedIds, allPageSelected, onTogglePage, onToggleRow,
  onView, onCopy, onPost, onUnpost, onVoidPayment, actionPending,
}: JournalRegisterTableProps) {
  return (
    <Table stickyHeader className="workspace-journal-table min-w-[970px]" containerClassName="workspace-table-scroll max-h-[60vh] overflow-auto border-0 shadow-none print:max-h-none print:overflow-visible">
      <THead>
        <TR className="whitespace-nowrap">
          <TH className="w-10"><input type="checkbox" aria-label="Select all journals on this page" checked={allPageSelected} onChange={onTogglePage} /></TH>
          <TH>Journal</TH>
          <TH>Date</TH>
          <TH>Source document</TH>
          <TH>Description</TH>
          <TH numeric>Debit</TH>
          <TH numeric>Credit</TH>
          <TH>Status</TH>
          <TH className="w-[110px]" numeric>Actions</TH>
        </TR>
      </THead>
      <TBody>
        {loading && <TR><TD colSpan={9} className="py-10 text-center text-slate-500">Loading journals…</TD></TR>}
        {error && <TR><TD colSpan={9} className="py-10 text-center text-red-700">Journals could not be loaded. Use Refresh to try again.</TD></TR>}
        {!loading && !error && rows.length === 0 && <TR><TD colSpan={9} className="py-10 text-center text-slate-500">No journals match these filters.</TD></TR>}
        {rows.map((row) => {
          const sourcePath = sourceDocumentPath(row.reference_type, row.reference_id);
          const difference = Number(row.difference ?? Number(row.total_debit) - Number(row.total_credit));
          const isUnbalanced = Math.abs(difference) > 0.005;
          const isSelected = selectedIds.includes(row.id);
          return (
            <TR key={row.id} className="whitespace-nowrap" aria-selected={isSelected}>
              <TD><input type="checkbox" aria-label={`Select ${row.journal_number}`} checked={isSelected} onChange={() => onToggleRow(row.id)} /></TD>
              <TD>
                <div className="flex min-w-0 flex-col gap-0.5">
                  <Link to={`/journal-entries/${row.id}`} className="font-semibold text-slate-800 hover:text-emerald-700 hover:underline">{row.journal_number}</Link>
                  <span className="max-w-[180px] truncate text-[11px] text-slate-500" title={row.reference_type?.replaceAll("_", " ")}>{row.reference_type?.replaceAll("_", " ") || "Manual"}</span>
                </div>
              </TD>
              <TD className="text-slate-600">{row.journal_date}</TD>
              <TD className="max-w-[220px] truncate font-medium">
                {sourcePath ? <Link className="text-emerald-700 hover:underline" to={sourcePath} state={{ returnTo: `/journal-entries/${row.id}` }} title="Open source document">{row.reference_number || "Open source"}</Link> : (row.reference_number || "—")}
              </TD>
              <TD className="max-w-[290px]"><span className="block truncate text-slate-600" title={row.description || undefined}>{row.description || "—"}</span></TD>
              <TD numeric className="tabular-nums font-medium">{amount(row.total_debit)}</TD>
              <TD numeric className="tabular-nums font-medium">{amount(row.total_credit)}</TD>
              <TD>
                <div className="flex flex-col items-start gap-1">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${row.status === "POSTED" ? "bg-emerald-50 text-emerald-800" : row.status === "DRAFT" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>{row.status}</span>
                  {isUnbalanced ? <span className="text-[11px] font-medium text-red-700" title="Debit minus credit">Difference {amount(difference)}</span> : <span className={`text-[11px] ${row.period_locked ? "text-slate-500" : row.accounting_recognized ? "text-emerald-700" : "text-amber-700"}`} title={row.recognition_reason ?? row.period_name ?? undefined}>{journalAccountingLabel(row)}</span>}
                </div>
              </TD>
              <TD numeric>
                <div className="flex items-center justify-end gap-1">
                  <Button size="xs" variant="outline" onClick={() => onView(row.id)}>Open</Button>
                  {(row.allowed_actions?.can_copy || row.allowed_actions?.can_post || row.allowed_actions?.can_unpost || row.allowed_actions?.can_void_source_payment) && (
                    <Dropdown.Root>
                      <Dropdown.Trigger type="button" aria-label={`More actions for ${row.journal_number}`} title="More journal actions" disabled={actionPending} className="grid h-8 w-8 place-items-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40"><MoreHorizontal size={16} /></Dropdown.Trigger>
                      <Dropdown.Portal>
                        <Dropdown.Content align="end" sideOffset={5} className="z-50 min-w-[165px] rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                          {row.allowed_actions?.can_copy && <Dropdown.Item className={menuItem} disabled={actionPending} onSelect={() => onCopy(row.id)}>Copy as new journal</Dropdown.Item>}
                          {row.allowed_actions?.can_post && <Dropdown.Item className={menuItem} disabled={actionPending} onSelect={() => onPost(row.id)}>Post journal</Dropdown.Item>}
                          {row.allowed_actions?.can_unpost && <Dropdown.Item className={menuItem} disabled={actionPending} onSelect={() => onUnpost(row.id)}>Unpost journal</Dropdown.Item>}
                          {row.allowed_actions?.can_void_source_payment && <Dropdown.Item className={`${menuItem} text-red-700`} disabled={actionPending} onSelect={() => onVoidPayment(row)}>Void source payment</Dropdown.Item>}
                        </Dropdown.Content>
                      </Dropdown.Portal>
                    </Dropdown.Root>
                  )}
                </div>
              </TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

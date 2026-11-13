import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import { Link } from "react-router-dom";
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
    <Table stickyHeader className="workspace-journal-table w-full min-w-[1780px] table-fixed" containerClassName="workspace-table-scroll max-h-[60vh] overflow-auto border-0 shadow-none print:max-h-none print:overflow-visible">
      <THead>
        <TR className="whitespace-nowrap">
          <TH className="w-[38px]"><input type="checkbox" aria-label="Select all journals on this page" checked={allPageSelected} onChange={onTogglePage} /></TH>
          <TH className="w-[175px]">Journal</TH>
          <TH className="w-[100px]">Date</TH>
          <TH className="w-[175px]">Document</TH>
          <TH className="w-[265px]">Description</TH>
          <TH className="w-[140px]" numeric>Debit</TH>
          <TH className="w-[140px]" numeric>Credit</TH>
          <TH className="w-[115px]" numeric>Difference</TH>
          <TH className="w-[90px]">Status</TH>
          <TH className="w-[120px]">Source</TH>
          <TH className="w-[120px]">Unit</TH>
          <TH className="w-[115px]">Location</TH>
          <TH className="w-[125px]">Department</TH>
          <TH className="w-[115px]">Created by</TH>
          <TH className="sticky right-0 z-20 w-[50px] bg-slate-50 text-right">Action</TH>
        </TR>
      </THead>
      <TBody>
        {loading && <TR><TD colSpan={15} className="py-10 text-center text-slate-500">Loading journals…</TD></TR>}
        {error && <TR><TD colSpan={15} className="py-10 text-center text-red-700">Journals could not be loaded. Use Refresh to try again.</TD></TR>}
        {!loading && !error && rows.length === 0 && <TR><TD colSpan={15} className="py-10 text-center text-slate-500">No journals match these filters.</TD></TR>}
        {rows.map((row) => {
          const sourcePath = sourceDocumentPath(row.reference_type, row.reference_id);
          const difference = Number(row.difference ?? Number(row.total_debit) - Number(row.total_credit));
          const isUnbalanced = Math.abs(difference) > 0.005;
          const isSelected = selectedIds.includes(row.id);
          return (
            <TR key={row.id} className="whitespace-nowrap" aria-selected={isSelected}>
              <TD><input type="checkbox" aria-label={`Select ${row.journal_number}`} checked={isSelected} onChange={() => onToggleRow(row.id)} /></TD>
              <TD className="max-w-0">
                <Link to={`/journal-entries/${row.id}`} onClick={(event) => {
                  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                  event.preventDefault();
                  onView(row.id);
                }} title={`Open journal ${row.journal_number}`} className="block truncate font-semibold text-emerald-800 hover:underline">{row.journal_number}</Link>
              </TD>
              <TD className="text-slate-600">{row.journal_date}</TD>
              <TD className="max-w-0 font-semibold">
                {sourcePath ? <Link className="block truncate text-slate-800 hover:text-emerald-700 hover:underline" to={sourcePath} state={{ returnTo: `/journal-entries/${row.id}` }} title={row.reference_number || "Open source document"}>{row.reference_number || "Open source"}</Link> : <span className="block truncate text-slate-700" title={row.reference_number || undefined}>{row.reference_number || "—"}</span>}
              </TD>
              <TD className="max-w-0"><span className="block truncate font-medium text-slate-800" title={row.description || undefined}>{row.description || "—"}</span></TD>
              <TD numeric className="tabular-nums font-semibold text-slate-900">{amount(row.total_debit)}</TD>
              <TD numeric className="tabular-nums font-semibold text-slate-900">{amount(row.total_credit)}</TD>
              <TD numeric className={`tabular-nums ${isUnbalanced ? "font-semibold text-red-700" : "text-slate-400"}`} title="Debit minus credit">{amount(difference)}</TD>
              <TD title={[journalAccountingLabel(row), row.recognition_reason, row.period_name].filter(Boolean).join(" · ")}>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${row.status === "POSTED" ? "bg-emerald-50 text-emerald-800" : row.status === "DRAFT" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>{row.status}</span>
              </TD>
              <TD className="max-w-0"><span className="block truncate text-xs text-slate-500" title={row.reference_type?.replaceAll("_", " ")}>{row.reference_type?.replaceAll("_", " ") || "—"}</span></TD>
              <TD className="max-w-0"><span className="block truncate text-xs text-slate-500" title={row.business_unit_name || undefined}>{row.business_unit_name || "—"}</span></TD>
              <TD className="max-w-0"><span className="block truncate text-xs text-slate-500" title={row.location_name || undefined}>{row.location_name || "—"}</span></TD>
              <TD className="max-w-0"><span className="block truncate text-xs text-slate-500" title={row.department_name || undefined}>{row.department_name || "—"}</span></TD>
              <TD className="max-w-0"><span className="block truncate text-xs text-slate-500" title={row.created_by_name || undefined}>{row.created_by_name || "—"}</span></TD>
              <TD numeric className="sticky right-0 z-[6] bg-white shadow-[-1px_0_0_#e6ebef]">
                <Dropdown.Root>
                  <Dropdown.Trigger type="button" aria-label={`Actions for ${row.journal_number}`} title="Journal actions" disabled={actionPending} className="grid h-7 w-7 place-items-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40"><MoreHorizontal size={16} /></Dropdown.Trigger>
                  <Dropdown.Portal>
                    <Dropdown.Content align="end" sideOffset={5} className="z-50 min-w-[165px] rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                      <Dropdown.Item className={menuItem} onSelect={() => onView(row.id)}>Open journal</Dropdown.Item>
                      {row.allowed_actions?.can_copy && <Dropdown.Item className={menuItem} disabled={actionPending} onSelect={() => onCopy(row.id)}>Copy as new journal</Dropdown.Item>}
                      {row.allowed_actions?.can_post && <Dropdown.Item className={menuItem} disabled={actionPending} onSelect={() => onPost(row.id)}>Post journal</Dropdown.Item>}
                      {row.allowed_actions?.can_unpost && <Dropdown.Item className={menuItem} disabled={actionPending} onSelect={() => onUnpost(row.id)}>Unpost journal</Dropdown.Item>}
                      {row.allowed_actions?.can_void_source_payment && <Dropdown.Item className={`${menuItem} text-red-700`} disabled={actionPending} onSelect={() => onVoidPayment(row)}>Void source payment</Dropdown.Item>}
                    </Dropdown.Content>
                  </Dropdown.Portal>
                </Dropdown.Root>
              </TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

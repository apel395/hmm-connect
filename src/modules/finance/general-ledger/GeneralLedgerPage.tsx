import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import SearchableSelect from "@/components/form/SearchableSelect";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listLocations } from "@/modules/admin/organization/api";
import { getAccountSummary, listLedger } from "./api";

const amount = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID");

export default function GeneralLedgerPage() {
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<any>({ search: searchParams.get("search") || "", account_id: searchParams.get("account_id") || "", date_from: searchParams.get("date_from") || "", date_to: searchParams.get("date_to") || "", reference_type: searchParams.get("reference_type") || "", supplier_id: searchParams.get("supplier_id") || "", department_id: searchParams.get("department_id") || "", location_id: searchParams.get("location_id") || "", business_unit_id: searchParams.get("business_unit_id") || "" });
  const params = Object.fromEntries(Object.entries({ ...filters, page, page_size: 20 }).filter(([, value]) => value !== ""));
  const ledger = useQuery({ queryKey: ["general-ledger", params], queryFn: () => listLedger(params) });
  const locations = useQuery({ queryKey: ["ledger-filter-locations", "active"], queryFn: () => listLocations({ is_active: true }) });
  const accounts = useQuery({ queryKey: ["ledger-accounts"], queryFn: () => getAccountLookup({ is_posting: true, is_active: true }) });
  const summary = useQuery({ queryKey: ["ledger-summary", filters.account_id, filters.date_from, filters.date_to], queryFn: () => getAccountSummary(Number(filters.account_id), { date_from: filters.date_from || undefined, date_to: filters.date_to || undefined }), enabled: !!filters.account_id });
  const change = (key: string, value: string) => { setFilters({ ...filters, [key]: value }); setPage(1); };
  const input = "h-10 rounded border px-3";

  return <div className="space-y-6"><PageHeader title="General Ledger" description="Read-only posted journal activity with server-calculated balances."/>
    <Card><div className="grid gap-3 md:grid-cols-4"><input className={input} placeholder="Search journal, document, description" value={filters.search} onChange={event => change("search", event.target.value)}/><select className={input} value={filters.account_id} onChange={event => change("account_id", event.target.value)}><option value="">All accounts</option>{accounts.data?.map(account => <option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select><input className={input} type="date" value={filters.date_from} onChange={event => change("date_from", event.target.value)}/><input className={input} type="date" value={filters.date_to} onChange={event => change("date_to", event.target.value)}/><select className={input} value={filters.reference_type} onChange={event => change("reference_type", event.target.value)}><option value="">All document types</option><option>SUPPLIER_INVOICE</option><option>SUPPLIER_PAYMENT</option><option>MANUAL</option></select><input className={input} placeholder="Supplier ID" value={filters.supplier_id} onChange={event => change("supplier_id", event.target.value)}/><input className={input} placeholder="Department ID" value={filters.department_id} onChange={event => change("department_id", event.target.value)}/><div><SearchableSelect label="Location" value={filters.location_id ? Number(filters.location_id) : undefined} disabled={locations.isLoading} placeholder={locations.isLoading ? "Loading locations..." : "Type location code or name..."} options={(locations.data ?? []).map((item: any) => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code ?? "", item.name ?? ""] }))} onChange={(id) => change("location_id", id ? String(id) : "")} /></div></div></Card>
    {summary.data && <Card><div className="grid gap-4 text-right md:grid-cols-4"><div><small>Opening Balance</small><div className="font-bold tabular-nums">{amount(summary.data.opening_balance)}</div></div><div><small>Total Debit</small><div className="font-bold tabular-nums">{amount(summary.data.total_debit)}</div></div><div><small>Total Credit</small><div className="font-bold tabular-nums">{amount(summary.data.total_credit)}</div></div><div><small>Closing Balance</small><div className="font-bold tabular-nums">{amount(summary.data.closing_balance)}</div></div></div></Card>}
    <Card>
      <Table variant="grid" stickyHeader className="min-w-[980px]" containerClassName="border-0 shadow-none">
        <THead><TR className="whitespace-nowrap"><TH>Date</TH><TH>Journal</TH><TH>Account</TH><TH>Description</TH><TH>Document</TH><TH numeric>Debit</TH><TH numeric>Credit</TH><TH numeric>Balance</TH><TH>Context</TH></TR></THead>
        <TBody>{ledger.data?.items.map((row: any) => {
          const contextPrimary = row.supplier_name || row.business_unit_name;
          const contextSecondary = [row.department_name, row.location_name].filter(Boolean).join(" · ");
          return <TR key={row.id}>
            <TD className="whitespace-nowrap">{row.posting_date}</TD>
            <TD className="whitespace-nowrap"><Link className={TABLE_UI.documentLink} to={`/journal-entries/${row.journal_id}`}>{row.journal_number}</Link></TD>
            <TD className="max-w-[200px]"><TableCellStack primary={row.account_name} secondary={row.account_code}/></TD>
            <TD className="max-w-[220px]"><span className="block truncate" title={row.description || undefined}>{row.description || "—"}</span></TD>
            <TD className="max-w-[160px]"><span className="block truncate font-medium text-slate-700" title={row.reference_number || undefined}>{row.reference_number || "—"}</span></TD>
            <TD numeric className="whitespace-nowrap">{amount(row.debit)}</TD>
            <TD numeric className="whitespace-nowrap">{amount(row.credit)}</TD>
            <TD numeric className="whitespace-nowrap font-semibold">{amount(row.balance)}</TD>
            <TD className="max-w-[180px]">{contextPrimary || contextSecondary ? <TableCellStack primary={contextPrimary || contextSecondary} secondary={contextPrimary ? contextSecondary : undefined}/> : "—"}</TD>
          </TR>;
        })}</TBody>
      </Table>
      <div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!ledger.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!ledger.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div>
    </Card>
  </div>;
}

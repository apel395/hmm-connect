import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";

import { getAuditReport } from "./reportApi";

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [documentNumber, setDocumentNumber] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: [
      "audit-events",
      documentType,
      page,
      pageSize,
      documentNumber,
      dateFrom,
      dateTo,
      action,
      actor,
    ],
    queryFn: () =>
      getAuditReport({
        page,
        pageSize,
        documentNumber,
        documentType,
        action,
        actor,
        dateFrom,
        dateTo,
      }),
    placeholderData: (previousData) => previousData,
  });

  const events = data?.items ?? [];
  const totalItems = data?.total_items ?? 0;
  const totalPages = data?.total_pages ?? 0;
  const firstRecord = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRecord = totalItems === 0 ? 0 : Math.min(page * pageSize, totalItems);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Log"
        description="Append-only document and workflow activity."
      />

      <Card className="p-5">
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
          <Input
            placeholder="Document number"
            value={documentNumber}
            onChange={(event) => {
              setDocumentNumber(event.target.value);
              setPage(1);
            }}
          />
          <select
            className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
            value={documentType}
            onChange={(event) => {
              setDocumentType(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All document types</option>
            <option value="PR">PR</option>
            <option value="PO">PO</option>
            <option value="GR">Goods Receipt</option>
          </select>
          <Input
            placeholder="Action"
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
          />
          <Input
            placeholder="User name"
            value={actor}
            onChange={(event) => {
              setActor(event.target.value);
              setPage(1);
            }}
          />
          <Input
            type="date"
            aria-label="From date"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value);
              setPage(1);
            }}
          />
          <Input
            type="date"
            aria-label="To date"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-12"><Loading /></div>
        ) : (
          <Table className="min-w-[900px]" containerClassName="rounded-none border-0 shadow-none">
            <THead><TR className="whitespace-nowrap"><TH>Time</TH><TH>User</TH><TH>Document</TH><TH>Event</TH><TH>Description</TH></TR></THead>
            <TBody className={isFetching ? "opacity-60" : undefined}>
              {events.map((event) => <TR key={event.id} className="align-top">
                <TD className="whitespace-nowrap">{new Date(event.occurred_at).toLocaleString()}</TD>
                <TD><TableCellStack primary={event.actor_name ?? "System"} secondary={(event.role_names ?? []).join(", ") || undefined}/></TD>
                <TD className="font-medium">{event.document_type ?? event.entity_type} {event.document_number ?? `#${event.entity_id}`}</TD>
                <TD><TableCellStack primary={event.action} secondary={event.document_status ?? undefined}/></TD>
                <TD className="max-w-[360px]"><span className="block truncate" title={event.summary}>{event.summary}</span></TD>
              </TR>)}
              {events.length === 0 && <TR><TD colSpan={5} className="py-12 text-center">No audit events found.</TD></TR>}
            </TBody>
          </Table>
        )}
        {!isLoading && (
          <div className="flex flex-col gap-3 border-t px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-slate-600">
              Showing {firstRecord}–{lastRecord} of {totalItems} records
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                Page size
                <select
                  className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value));
                    setPage(1);
                  }}
                >
                  {[10, 20, 50, 100].map((size) => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
              </label>
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage(1)}
              >
                First
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span className="px-2 text-sm text-slate-700">
                Page {page} of {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!data?.has_next}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!data?.has_next}
                onClick={() => setPage(totalPages)}
              >
                Last
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

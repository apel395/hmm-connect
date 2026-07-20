import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";
import { getAuditLogs, type AuditLog } from "../features/audit-logs/auditLogsApi";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function getActionClass(action: string) {
  if (action.includes("DELETE") || action.includes("REJECT")) return "bg-red-50 text-red-700 ring-red-600/10";
  if (action.includes("APPROVE") || action.includes("RECEIVE") || action.includes("CREATE")) return "bg-emerald-50 text-emerald-700 ring-emerald-600/10";
  if (action.includes("UPDATE")) return "bg-blue-50 text-blue-700 ring-blue-600/10";
  return "bg-slate-100 text-slate-700 ring-slate-500/10";
}

function getEntityLabel(entityType: string) {
  return entityType.replaceAll("_", " ");
}

function AuditRow({ log }: { log: AuditLog }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return <>
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50"><td className="px-6 py-4 text-sm text-slate-500">{formatDate(log.created_at)}</td><td className="px-6 py-4"><p className="text-sm font-medium text-slate-900">{log.actor_name || log.user_name || "System"}</p><p className="mt-1 text-xs text-slate-500">{[log.department_name, log.location_name, log.role_names.join(", ")].filter(Boolean).join(" · ") || "No identity context"}</p></td><td className="px-6 py-4"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${getActionClass(log.action)}`}>{log.action.replaceAll("_", " ")}</span></td><td className="px-6 py-4 text-sm text-slate-600">{getEntityLabel(log.entity_type)}{log.entity_id ? ` #${log.entity_id}` : ""}</td><td className="px-6 py-4 text-sm text-slate-700">{log.summary}</td><td className="px-6 py-4 text-right">{log.details && <button type="button" onClick={() => setIsExpanded((value) => !value)} className="text-xs font-medium text-slate-600 hover:text-slate-900">{isExpanded ? "Hide" : "Details"}</button>}</td></tr>
    {isExpanded && log.details && <tr className="border-b border-slate-100 bg-slate-50"><td colSpan={6} className="px-6 py-4"><pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">{JSON.stringify(log.details, null, 2)}</pre></td></tr>}
  </>;
}

export default function AuditLogsPage() {
  const [actionFilter, setActionFilter] = useState("ALL");
  const [entityFilter, setEntityFilter] = useState("ALL");
  const auditLogsQuery = useQuery({ queryKey: ["audit-logs"], queryFn: getAuditLogs });
  const actions = useMemo(() => Array.from(new Set((auditLogsQuery.data ?? []).map((log) => log.action))).sort(), [auditLogsQuery.data]);
  const entities = useMemo(() => Array.from(new Set((auditLogsQuery.data ?? []).map((log) => log.entity_type))).sort(), [auditLogsQuery.data]);
  const auditLogs = auditLogsQuery.data ?? [];
  const filteredLogs = auditLogs.filter((log) => (actionFilter === "ALL" || log.action === actionFilter) && (entityFilter === "ALL" || log.entity_type === entityFilter));

  return <div className="space-y-6"><PageHeader title="Audit Log" description="Review important changes and workflow actions. Audit history is immutable." />
    <div className="rounded-xl border border-slate-200 bg-white"><div className="flex flex-col gap-4 border-b border-slate-200 p-6 lg:flex-row lg:items-center lg:justify-between"><div><h2 className="font-semibold text-slate-900">Activity history</h2><p className="mt-1 text-sm text-slate-500">{filteredLogs.length} audit entries</p></div><div className="grid gap-3 sm:grid-cols-2"><Select value={actionFilter} onChange={setActionFilter} options={[{ value: "ALL", label: "All actions" }, ...actions.map((action) => ({ value: action, label: action.replaceAll("_", " ") }))]} /><Select value={entityFilter} onChange={setEntityFilter} options={[{ value: "ALL", label: "All entities" }, ...entities.map((entity) => ({ value: entity, label: getEntityLabel(entity) }))]} /></div></div>
      {auditLogsQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading audit log...</div>}
      {auditLogsQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load audit log.</div>}
      {!auditLogsQuery.isLoading && !auditLogsQuery.isError && filteredLogs.length === 0 && <EmptyState title="No audit entries found" description="Try changing the filters or perform a business action to create an audit event." />}
      {filteredLogs.length > 0 && <div className="overflow-x-auto"><table className="w-full min-w-[1000px]"><thead><tr className="border-b border-slate-200 text-left"><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Date</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">User</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Action</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Entity</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</th><th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Details</th></tr></thead><tbody>{filteredLogs.map((log) => <AuditRow key={log.id} log={log} />)}</tbody></table></div>}
    </div>
  </div>;
}

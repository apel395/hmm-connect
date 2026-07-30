import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";

export default function AuditLogPage() {
  const [documentNumber, setDocumentNumber] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["audit-events", documentNumber, documentType, action, actor],
    queryFn: async () => {
      const response = await api.get("/audit/events", {
        params: {
          document_number: documentNumber || undefined,
          document_type: documentType || undefined,
          action: action || undefined,
          actor: actor || undefined,
        },
      });
      return response.data;
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Log"
        description="Append-only document and workflow activity."
      />

      <Card className="p-5">
        <div className="grid gap-4 md:grid-cols-4">
          <Input
            placeholder="Document number"
            value={documentNumber}
            onChange={(event) => setDocumentNumber(event.target.value)}
          />
          <select
            className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value)}
          >
            <option value="">All document types</option>
            <option value="PR">PR</option>
            <option value="PO">PO</option>
            <option value="GR">Goods Receipt</option>
          </select>
          <Input
            placeholder="Action"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          />
          <Input
            placeholder="User name"
            value={actor}
            onChange={(event) => setActor(event.target.value)}
          />
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-12"><Loading /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left">Time</th>
                  <th className="px-4 py-3 text-left">User / Roles</th>
                  <th className="px-4 py-3 text-left">Document</th>
                  <th className="px-4 py-3 text-left">Action</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Description</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event: any) => (
                  <tr key={event.id} className="border-t align-top">
                    <td className="px-4 py-3 whitespace-nowrap">
                      {new Date(event.occurred_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div>{event.actor_name ?? "System"}</div>
                      <div className="text-xs text-slate-500">
                        {(event.role_names ?? []).join(", ") || "-"}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {event.document_type ?? event.entity_type}
                      {" "}
                      {event.document_number ?? `#${event.entity_id}`}
                    </td>
                    <td className="px-4 py-3">{event.action}</td>
                    <td className="px-4 py-3">{event.document_status ?? "-"}</td>
                    <td className="px-4 py-3">{event.summary}</td>
                  </tr>
                ))}
                {events.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-12 text-center">No audit events found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
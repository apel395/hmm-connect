import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import { Printer } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import api from "@/api/client";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import PageHeader from "@/components/common/PageHeader";

export default function TraceabilityPage() {
  const { documentType, id } = useParams();
  const navigate = useNavigate();
  const endpointType = documentType === "po" ? "purchase-orders" : "purchase-requisitions";

  const { data, isLoading } = useQuery({
    queryKey: ["traceability", documentType, id],
    queryFn: async () => {
      const response = await api.get(`/traceability/${endpointType}/${id}`);
      return response.data;
    },
    enabled: Boolean(id),
  });

  if (isLoading) return <Loading />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Traceability: ${data.document.number}`}
        description="Document approvals, downstream documents, stock movements, and audit events."
        actions={<>
<WorkspaceBackButton />
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}
      />

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-slate-500">Source Document</div>
            <div className="text-xl font-semibold">{data.document.number}</div>
          </div>
          <Badge>{data.document.status}</Badge>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Approval Steps</h2>
          <div className="space-y-3">
            {(data.approval?.steps ?? []).map((step: any) => (
              <div key={step.step_order} className="rounded border p-3">
                <div className="font-medium">{step.step_order}. {step.name}</div>
                <div className="text-sm text-slate-600">
                  {step.required_role} — {step.status}
                </div>
                <div className="text-xs text-slate-500">
                  {step.decided_by
                    ? `${step.status === "REJECTED" ? "Rejected" : "Approved"} by ${step.decided_by} as ${step.decided_as}`
                    : `Waiting for ${step.required_role}`}
                </div>
                {step.decided_at && (
                  <div className="text-xs text-slate-400">
                    {new Date(step.decided_at).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Downstream Documents</h2>
          <div className="space-y-3">
            {(data.purchase_orders ?? []).map((order: any) => (
              <div key={order.id} className="rounded border p-3">
                <div className="font-medium">{order.number}</div>
                <div className="text-sm">{order.status} · {order.supplier}</div>
              </div>
            ))}
            {(data.goods_receipts ?? []).map((receipt: any) => (
              <div key={receipt.id} className="rounded border p-3">
                <div className="font-medium">{receipt.number}</div>
                <div className="text-sm">{receipt.destination_type ?? "Receipt"}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="border-b bg-slate-50 px-5 py-4 font-semibold">Activity Timeline</div>
        <div className="divide-y">
          {(data.events ?? []).map((event: any) => (
            <div key={event.id} className="grid gap-2 px-5 py-4 md:grid-cols-4">
              <div className="text-sm">{new Date(event.occurred_at).toLocaleString()}</div>
              <div className="font-medium">{event.action}</div>
              <div>{event.actor_name ?? "System"}</div>
              <div className="text-sm text-slate-600">{event.summary}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useParams } from "react-router-dom";

import api from "@/api/client";
import ModuleSummary from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import { apiErrorMessage } from "@/utils/apiError";

function statusVariant(status?: string | null): BadgeVariant {
  if (!status) return "default";
  if (/APPROVED|POSTED|RECEIVED|COMPLETED|CLOSED/i.test(status)) return "success";
  if (/REJECTED|CANCELLED|CANCELED|VOID/i.test(status)) return "danger";
  if (/PENDING|WAITING|DRAFT/i.test(status)) return "warning";
  return "default";
}

function statePage(content: ReactNode, title = "Traceability") {
  return <DataWorkspace area="Admin">
    <div className="workspace-body">
      <PageHeader title={title} description="Document approvals, downstream documents, stock movements, and audit events." />
      {content}
    </div>
  </DataWorkspace>;
}

export default function TraceabilityPage() {
  const { documentType, id } = useParams();
  
  const endpointType = documentType === "po" ? "purchase-orders" : "purchase-requisitions";

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["traceability", documentType, id],
    queryFn: async () => {
      const response = await api.get(`/traceability/${endpointType}/${id}`);
      return response.data;
    },
    enabled: Boolean(id),
  });

  if (isLoading) return statePage(<div className="py-12"><Loading message="Loading traceability…"/></div>);
  if (isError) return statePage(<div role="alert" className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700"><p className="font-semibold">Traceability could not be loaded.</p><p>{apiErrorMessage(error, "Please try again.")}</p></div>);
  if (!data) return statePage(<Empty title="No traceability data" description="Select a document with an audit trail to view its history." />);

  const steps = data.approval?.steps ?? [];
  const purchaseOrders = data.purchase_orders ?? [];
  const goodsReceipts = data.goods_receipts ?? [];
  const events = data.events ?? [];

  return (
    <DataWorkspace area="Admin">
      <div className="workspace-body">
        <PageHeader
          title={`Traceability: ${data.document.number}`}
          description="Document approvals, downstream documents, stock movements, and audit events."
          actions={<>
  <WorkspaceBackButton />
  <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
  </>}
        />

        <ModuleSummary metrics={[
          { label: "Approval Steps", value: steps.length },
          { label: "Decisions", value: steps.filter((step: any) => Boolean(step.decided_by)).length },
          { label: "Downstream Documents", value: purchaseOrders.length + goodsReceipts.length },
          { label: "Audit Events", value: events.length },
        ]}/>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">Source Document</div>
              <div className="text-xl font-semibold">{data.document.number}</div>
            </div>
            <Badge variant={statusVariant(data.document.status)}>{data.document.status}</Badge>
          </div>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <h2 className="mb-4 font-semibold">Approval Steps</h2>
            <div className="space-y-3">
              {steps.length === 0 ? <Empty className="py-6" title="No approval steps" description="This document has no recorded approval steps." /> : steps.map((step: any) => (
                <div key={step.step_order} className="rounded border p-3">
                  <div className="font-medium">{step.step_order}. {step.name}</div>
                  <div className="text-sm text-slate-600">
                    {step.required_role} — <Badge variant={statusVariant(step.status)}>{step.status}</Badge>
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
              {purchaseOrders.map((order: any) => (
                <div key={order.id} className="rounded border p-3">
                  <div className="font-medium">{order.number}</div>
                  <div className="text-sm"><Badge variant={statusVariant(order.status)}>{order.status}</Badge> · {order.supplier}</div>
                </div>
              ))}
              {goodsReceipts.map((receipt: any) => (
                <div key={receipt.id} className="rounded border p-3">
                  <div className="font-medium">{receipt.number}</div>
                  <div className="text-sm">{receipt.destination_type ?? "Receipt"}</div>
                </div>
              ))}
              {purchaseOrders.length === 0 && goodsReceipts.length === 0 && <Empty className="py-6" title="No downstream documents" description="No purchase orders or goods receipts were created from this document." />}
            </div>
          </Card>
        </div>

        <Card className="overflow-hidden p-0">
          <div className="border-b bg-slate-50 px-5 py-4 font-semibold">Activity Timeline</div>
          <div className="divide-y">
            {events.length === 0 ? <Empty className="py-6" title="No activity recorded" description="There are no audit events for this document yet." /> : events.map((event: any) => (
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
    </DataWorkspace>
  );
}

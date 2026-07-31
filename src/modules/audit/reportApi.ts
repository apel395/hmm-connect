import api from "@/api/client";

import {
  AuditEvent,
  AuditReportParams,
  PaginatedReportResponse,
} from "./reportTypes";

export async function getAuditReport({
  page,
  pageSize,
  documentNumber,
  documentType,
  action,
  actor,
  dateFrom,
  dateTo,
}: AuditReportParams): Promise<PaginatedReportResponse<AuditEvent>> {
  const response = await api.get<PaginatedReportResponse<AuditEvent>>(
    "/audit/events",
    {
      params: {
        page,
        page_size: pageSize,
        document_number: documentNumber || undefined,
        document_type: documentType || undefined,
        action: action || undefined,
        actor: actor || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
    },
  );

  return response.data;
}

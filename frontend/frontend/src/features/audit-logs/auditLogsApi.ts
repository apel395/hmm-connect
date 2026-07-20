import api from "../../api/client";

export interface AuditLog {
  id: number;
  user_id: number | null;
  user_name: string | null;
  actor_name: string | null;
  department_id: number | null;
  department_name: string | null;
  location_id: number | null;
  location_name: string | null;
  role_names: string[];
  action: string;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export async function getAuditLogs(): Promise<AuditLog[]> {
  const response = await api.get<AuditLog[]>("/audit-logs", {
    params: { limit: 200 },
  });

  return response.data;
}

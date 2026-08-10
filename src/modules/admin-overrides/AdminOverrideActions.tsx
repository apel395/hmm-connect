import axios from "axios";
import { RotateCcw, Unlock } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import useAuthorization from "@/hooks/useAuthorization";

const detailMessage = (error: unknown, fallback: string) => {
  if (!axios.isAxiosError(error)) return fallback;
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  return fallback;
};

export function AdminReopenButton({
  entityType,
  entityId,
  status,
  onSuccess,
}: {
  entityType: string;
  entityId: number;
  status?: string | null;
  onSuccess?: () => void;
}) {
  const { isSuperuser } = useAuthorization();
  const normalized = String(status || "").toUpperCase();
  const mutation = useMutation({
    mutationFn: async () => (await api.post(`/admin-overrides/${entityType}/${entityId}/reopen`)).data,
    onSuccess: () => {
      toast.success("Document reopened for administrator correction.");
      onSuccess?.();
    },
    onError: (error) => toast.error(detailMessage(error, "Document could not be reopened.")),
  });

  if (!isSuperuser() || !normalized || ["DRAFT", "VOID", "CANCELLED"].includes(normalized)) return null;
  return <Button variant="outline" loading={mutation.isPending} onClick={() => mutation.mutate()}><RotateCcw size={16}/> Reopen for Correction</Button>;
}

export function AdminJournalUnpostButton({
  journalId,
  status,
  onSuccess,
}: {
  journalId: number;
  status?: string | null;
  onSuccess?: () => void;
}) {
  const { isSuperuser } = useAuthorization();
  const mutation = useMutation({
    mutationFn: async () => (await api.post(`/admin-overrides/journals/${journalId}/unpost`)).data,
    onSuccess: () => {
      toast.success("Journal unposted. The source document and General Ledger were synchronized.");
      onSuccess?.();
    },
    onError: (error) => toast.error(detailMessage(error, "Journal could not be unposted.")),
  });

  if (!isSuperuser() || String(status || "").toUpperCase() !== "POSTED") return null;
  return <Button variant="outline" loading={mutation.isPending} onClick={() => mutation.mutate()}><Unlock size={16}/> Admin Unpost</Button>;
}

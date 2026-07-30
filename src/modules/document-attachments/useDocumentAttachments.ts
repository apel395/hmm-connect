import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { attachmentApi } from "./attachmentApi";
import type { AttachmentEntityType, AttachmentUploadInput } from "./types";

export const attachmentKeys = {
  entity: (entityType: AttachmentEntityType, entityId: number) =>
    ["document-attachments", entityType, entityId] as const,
};

export function useDocumentAttachments(
  entityType: AttachmentEntityType,
  entityId: number,
) {
  return useQuery({
    queryKey: attachmentKeys.entity(entityType, entityId),
    queryFn: () => attachmentApi.list(entityType, entityId),
    enabled: entityId > 0,
  });
}

export function useUploadAttachment(
  entityType: AttachmentEntityType,
  entityId: number,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      input,
      onProgress,
    }: {
      input: AttachmentUploadInput;
      onProgress?: (percent: number) => void;
    }) => attachmentApi.upload(input, onProgress),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: attachmentKeys.entity(entityType, entityId),
      }),
  });
}

export function useDeleteAttachment(
  entityType: AttachmentEntityType,
  entityId: number,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: attachmentApi.remove,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: attachmentKeys.entity(entityType, entityId),
      }),
  });
}

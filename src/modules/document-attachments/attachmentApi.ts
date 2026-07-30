import api from "@/api/client";
import type {
  AttachmentEntityType,
  AttachmentUploadInput,
  DocumentAttachment,
} from "./types";

export const attachmentApi = {
  async list(
    entityType: AttachmentEntityType,
    entityId: number,
  ): Promise<DocumentAttachment[]> {
    const response = await api.get<DocumentAttachment[]>("/document-attachments", {
      params: { entity_type: entityType, entity_id: entityId },
    });
    return Array.isArray(response.data) ? response.data : [];
  },

  upload(input: AttachmentUploadInput, onProgress?: (percent: number) => void) {
    const form = new FormData();
    form.append("entity_type", input.entityType);
    form.append("entity_id", String(input.entityId));
    form.append("attachment_type", input.attachmentType);
    form.append("file", input.file);
    form.append("source_type", input.sourceType);
    if (input.documentNumber) form.append("document_number", input.documentNumber);
    if (input.documentDate) form.append("document_date", input.documentDate);
    if (input.description) form.append("description", input.description);

    return api.post<DocumentAttachment>("/document-attachments/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress(Math.round((event.loaded * 100) / event.total));
        }
      },
    });
  },

  download: (id: number) =>
    api.get<Blob>(`/document-attachments/${id}/download`, {
      responseType: "blob",
    }),

  remove: (id: number) =>
    api.delete<DocumentAttachment>(`/document-attachments/${id}`),
};

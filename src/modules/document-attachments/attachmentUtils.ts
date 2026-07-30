import axios from "axios";

interface ValidationDetail {
  loc?: Array<string | number>;
  msg?: string;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export function isPreviewableMimeType(mimeType?: string | null): boolean {
  return Boolean(
    mimeType === "application/pdf" ||
      mimeType?.startsWith("image/jpeg") ||
      mimeType?.startsWith("image/png") ||
      mimeType?.startsWith("image/webp"),
  );
}

export function extractDownloadFilename(
  contentDisposition: string | undefined,
  fallback: string,
): string {
  if (!contentDisposition) return fallback;
  const utf8 = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (utf8) return decodeURIComponent(utf8);
  return contentDisposition.match(/filename="?([^";]+)"?/i)?.[1] || fallback;
}

export function parseAttachmentError(error: unknown): string {
  if (!axios.isAxiosError(error)) return "The attachment request failed.";
  const status = error.response?.status;
  const data = error.response?.data as
    | { detail?: string | ValidationDetail[]; message?: string }
    | undefined;
  if (Array.isArray(data?.detail)) {
    const detail = data.detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        return [field, item.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join("; ");
    if (detail) return detail;
  }
  if (typeof data?.detail === "string") return data.detail;
  if (data?.message) return data.message;
  if (status === 400) return "The attachment request is invalid.";
  if (status === 404) return "The attachment was not found.";
  if (status === 409) return "This attachment has already been uploaded.";
  if (status === 413) return "The selected file is too large.";
  if (status === 415) return "This file type is not supported.";
  if (status === 422) return "Please check the attachment fields.";
  if (status && status >= 500) return "The server could not process the attachment.";
  return "The attachment request failed.";
}

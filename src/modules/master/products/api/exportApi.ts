import api from "@/api/interceptor";

export type ExportStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

export interface ExportJob {
  job_id: string;
  export_type: string;
  status: ExportStatus;
  filename?: string | null;
  error_message?: string | null;
  download_url?: string;
}

export const exportApi = {
  createProductsExport: (catalogType?: "CATERING" | "HOTEL") =>
    api.post<ExportJob>("/exports", { export_type: "products", params: { catalog_type: catalogType } }),

  getExport: (jobId: string) =>
    api.get<ExportJob>(`/exports/${jobId}`),
};

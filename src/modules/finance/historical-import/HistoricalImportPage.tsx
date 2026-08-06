import WorkerRequiredPage from "@/modules/system/WorkerRequiredPage";

export default function HistoricalImportPage() {
  return (
    <WorkerRequiredPage
      title="Historical Import"
      description="Bulk Excel validation and historical document processing run on the HMM Processing Service to keep the core application lightweight."
    />
  );
}

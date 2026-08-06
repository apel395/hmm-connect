import WorkerRequiredPage from "@/modules/system/WorkerRequiredPage";

export default function TrialBalancePage() {
  return (
    <WorkerRequiredPage
      title="Trial Balance Processing"
      description="Large trial-balance exports and spreadsheet generation require the HMM Processing Service."
    />
  );
}

import WorkerRequiredPage from "@/modules/system/WorkerRequiredPage";

export default function BudgetListPage() {
  return (
    <WorkerRequiredPage
      title="Budget Processing"
      description="Budget imports, recalculation, and large budget-versus-actual jobs require the HMM Processing Service."
    />
  );
}

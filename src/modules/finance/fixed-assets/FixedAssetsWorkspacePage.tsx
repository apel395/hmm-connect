import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import FixedAssetListPage from "./FixedAssetListPage";
import AssetCategoryPage from "./AssetCategoryPage";
import DepreciationRunsPage from "./DepreciationRunsPage";
import AmortizationPage from "./AmortizationPage";
import FixedAssetReportPage from "./FixedAssetReportPage";

type Section = "assets" | "categories" | "depreciation" | "amortization" | "reports";

const tabs = [
  { label: "Assets", to: "/fixed-assets", exact: true },
  { label: "Categories", to: "/fixed-assets/categories" },
  { label: "Depreciation", to: "/fixed-assets/depreciation" },
  { label: "Amortization", to: "/fixed-assets/amortization" },
  { label: "Reports", to: "/fixed-assets/reports" },
];

export default function FixedAssetsWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Fixed Assets"
        description="Manage assets, categories, depreciation, amortization, and asset reporting."
        tabs={tabs}
      />
      {section === "assets" && <FixedAssetListPage />}
      {section === "categories" && <AssetCategoryPage />}
      {section === "depreciation" && <DepreciationRunsPage />}
      {section === "amortization" && <AmortizationPage />}
      {section === "reports" && <FixedAssetReportPage />}
    </div>
  );
}

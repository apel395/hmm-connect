import PageHeader from "@/components/common/PageHeader";
import OrganizationManagement from "./OrganizationManagement";

export default function OrganizationDimensionsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Organization Dimensions" description="Manage the company hierarchy used by finance and operations." />
      <OrganizationManagement />
    </div>
  );
}

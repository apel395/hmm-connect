import DataWorkspace from "@/components/workspace/DataWorkspace";
import { useSearchParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Button from "@/components/ui/Button";
import OrganizationManagement, { OrganizationSection } from "./OrganizationManagement";

const pageCopy: Record<OrganizationSection, { title: string; description: string }> = {
  "business-units": {
    title: "Business Units",
    description: "Manage operating entities used across purchasing, inventory, finance, and reporting.",
  },
  departments: {
    title: "Departments",
    description: "Manage departments and their business-unit assignments.",
  },
  locations: {
    title: "Locations",
    description: "Manage hotel, office, warehouse, and operational locations.",
  },
};

interface Props {
  section?: OrganizationSection;
}

function normalizeSection(value: string | null): OrganizationSection | undefined {
  return value === "business-units" || value === "departments" || value === "locations"
    ? value
    : undefined;
}

export default function OrganizationDimensionsPage({ section: fixedSection }: Props) {
  const [searchParams] = useSearchParams();
  const section = fixedSection ?? normalizeSection(searchParams.get("section"));
  const copy = section
    ? pageCopy[section]
    : {
        title: "Organization Dimensions",
        description: "Manage the company hierarchy used by finance and operations.",
      };

  return (
    <DataWorkspace area="Master data" >
      <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title={copy.title} description={copy.description} />
      <OrganizationManagement fixedSection={section} />
    </DataWorkspace>
  );
}

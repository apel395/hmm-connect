import PageHeader from "@/components/common/PageHeader";
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

export default function OrganizationDimensionsPage({ section }: Props) {
  const copy = section
    ? pageCopy[section]
    : {
        title: "Organization Dimensions",
        description: "Manage the company hierarchy used by finance and operations.",
      };

  return (
    <div className="space-y-4">
      <PageHeader title={copy.title} description={copy.description} />
      <OrganizationManagement fixedSection={section} />
    </div>
  );
}

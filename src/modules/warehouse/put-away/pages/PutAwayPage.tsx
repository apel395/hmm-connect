import DataWorkspace from "@/components/workspace/DataWorkspace";
import PageHeader from "@/components/common/PageHeader";
import Empty from "@/components/ui/Empty";

/**
 * The deployed API has no Put Away endpoint: received stock is placed into
 * inventory when the goods receipt is posted. Keep the route, but fail closed
 * with an explicit message instead of requesting a missing resource.
 */
export default function PutAwayPage() {
  return (
    <DataWorkspace area="Inventory">
      <PageHeader
        title="Put Away"
        description="Warehouse placement for received stock."
      />
      <Empty
        title="Put Away is not available"
        description="Received stock is placed into inventory when the goods receipt is posted. Use Inventory to review current stock and locations."
      />
    </DataWorkspace>
  );
}

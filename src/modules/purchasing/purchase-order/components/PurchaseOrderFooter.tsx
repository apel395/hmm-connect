import Button from "@/components/ui/Button";

interface Props {
  loading?: boolean;
  editing?: boolean;
  onCancel: () => void;
  onSubmit: () => void;
}

export default function PurchaseOrderFooter({
  loading,
  editing = false,
  onCancel,
  onSubmit,
}: Props) {
  return (
    <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-slate-200 bg-white px-6 py-4">
      <Button variant="outline" onClick={onCancel}>
        Cancel
      </Button>
      <Button loading={loading} onClick={onSubmit}>
        {editing ? "Save Changes" : "Create Purchase Order"}
      </Button>
    </div>
  );
}

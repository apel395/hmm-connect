import { ArrowLeft } from "lucide-react";
import Button from "@/components/ui/Button";
import useWorkspaceBack from "@/hooks/useWorkspaceBack";

export default function WorkspaceBackButton() {
  const { back, disabled } = useWorkspaceBack();
  return <Button type="button" variant="outline" size="sm" onClick={back} disabled={disabled}
    title="Close current workspace tab" aria-label="Back and close current tab" className="print:hidden">
    <ArrowLeft size={15} aria-hidden="true" /> Back
  </Button>;
}

import Button from "@/components/ui/Button";
export default function FormRecoveryActions({ failed, onDiscard, disabled }: { failed: boolean; onDiscard: () => void; disabled?: boolean }) {
  return <div className="mr-auto flex items-center gap-2">
    <Button type="button" size="sm" variant="outline" disabled={disabled} onClick={() => { if (window.confirm("Discard unsaved input in this form?")) onDiscard(); }}>Discard input</Button>
    {failed ? <span role="alert" className="text-xs text-red-700">Browser recovery unavailable. Keep this form open until saved.</span> : null}
  </div>;
}

import { useEffect, useState } from "react";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Textarea from "@/components/ui/Textarea";

function rejectionMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return (error as { message?: string })?.message || "The request could not be rejected.";
}

interface Props {
  open: boolean;
  onClose: () => void;
  onReject: (reason: string) => Promise<void> | void;
  pending?: boolean;
  title?: string;
  label?: string;
}

/** Shared approval rejection dialog so every purchasing document collects a reason the same way. */
export default function RejectDialog({
  open,
  onClose,
  onReject,
  pending = false,
  title = "Reject Request",
  label = "Reason for rejection",
}: Props) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
      setError("");
    }
  }, [open]);

  const submit = async () => {
    const value = reason.trim();
    if (value.length < 3) {
      setError("Enter a rejection reason of at least 3 characters.");
      return;
    }
    setError("");
    try {
      await onReject(value);
    } catch (failure) {
      setError(rejectionMessage(failure));
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => !pending && !value && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-3">
          <label className="block text-sm font-medium" data-field="rejection_reason">
            {label} *
            <Textarea
              autoFocus
              rows={4}
              className="mt-1"
              value={reason}
              disabled={pending}
              error={Boolean(error)}
              onChange={(event) => {
                setReason(event.target.value);
                if (error) setError("");
              }}
            />
          </label>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" disabled={pending} onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={pending} disabled={!reason.trim()} onClick={submit}>
            Reject
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

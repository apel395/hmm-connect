import { useCallback, useEffect } from "react";

export default function useUnsavedFormChanges({
  dirty,
  busy,
  recoverable,
  onClose,
}: {
  dirty: boolean;
  busy: boolean;
  recoverable: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  return useCallback(() => {
    if (busy) return;
    if (dirty) {
      const message = recoverable
        ? "Your unfinished input is saved on this browser. Close the form and keep it for later?"
        : "Browser draft recovery is unavailable. Closing may lose your unfinished input. Close anyway?";
      if (!window.confirm(message)) return;
    }
    onClose();
  }, [busy, dirty, onClose, recoverable]);
}

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import useAuthStore from "@/store/auth";
import { draftKey, readDraft, writeDraft, removeDraft, browserDraftStorage } from "@/utils/formDraftStorage";

const memoryInputs = new Map<string, unknown>();

// Recovery is browser input, never a submitted/approved accounting document.
export default function useFormRecovery<T>(name: string, value: T, active: boolean, valid: (value: unknown) => value is T) {
  const owner = useAuthStore(state => state.user?.id ?? state.user?.username);
  const inputOwner = useRef(owner);
  if (inputOwner.current == null && owner != null) inputOwner.current = owner;
  const key = owner == null || owner !== inputOwner.current ? null : draftKey(String(owner), name);
  const [failed, setFailed] = useState(false);
  const latest = useRef({ key, value, active });
  latest.current = { key, value, active };
  const blocked = useRef<string | null>(null);
  const serialized = JSON.stringify(value);
  useEffect(() => {
    if (!active || !key || blocked.current === serialized) return;
    blocked.current = null;
    memoryInputs.set(key, latest.current.value);
    const storage = browserDraftStorage();
    const saved = storage ? writeDraft(storage, key, latest.current.value) : false;
    setFailed(!saved);
  }, [key, serialized, active]);
  useEffect(() => {
    const flush = () => {
      const current = latest.current;
      const storage = browserDraftStorage();
      if (current.active && current.key && blocked.current !== JSON.stringify(current.value)) {
        memoryInputs.set(current.key, current.value);
        if (storage) writeDraft(storage, current.key, current.value);
      }
    };
    window.addEventListener("pagehide", flush);
    return () => { flush(); window.removeEventListener("pagehide", flush); };
  }, []);
  return useMemo(() => ({
    load: (otherName?: string) => {
      if (owner == null || owner !== inputOwner.current) return null;
      const target = draftKey(String(owner), otherName ?? name), storage = browserDraftStorage();
      const saved = storage ? readDraft<T>(storage, target, valid) : null;
      const memory = memoryInputs.get(target);
      return valid(memory) ? memory : saved;
    },
    clear: () => { blocked.current = JSON.stringify(latest.current.value); const storage = browserDraftStorage(); if (key) { memoryInputs.delete(key); if (storage) removeDraft(storage, key); } },
    failed,
    notifyRestored: () => toast.success("Unsaved input restored"),
  }), [key, owner, name, failed, valid]);
}

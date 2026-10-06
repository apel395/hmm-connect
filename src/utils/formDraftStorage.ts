const VERSION = 1;
export const draftKey = (owner: string, form: string) => `hmm-form-input:v${VERSION}:${encodeURIComponent(owner)}:${encodeURIComponent(form)}`;
export function readDraft<T>(storage: Pick<Storage, "getItem" | "removeItem">, key: string, valid: (value: unknown) => value is T): T | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const entry = JSON.parse(raw);
    if (entry.version !== VERSION || !valid(entry.value)) { storage.removeItem(key); return null; }
    return entry.value;
  } catch { return null; }
}
export function writeDraft<T>(storage: Pick<Storage, "setItem">, key: string, value: T): boolean {
  try { storage.setItem(key, JSON.stringify({ version: VERSION, savedAt: new Date().toISOString(), value })); return true; }
  catch { return false; }
}
export function removeDraft(storage: Pick<Storage, "removeItem">, key: string): void { try { storage.removeItem(key); } catch { /* Memory input remains usable. */ } }
export function browserDraftStorage(): Storage | null { try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; } }

export type MasterDataKind = "products" | "suppliers";
const eventName = "mmh:master-data-changed";
const storageKey = "mmh-master-data-change";
export function publishMasterDataChange(kind: MasterDataKind) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(eventName, { detail: kind }));
  try { window.localStorage.setItem(storageKey, JSON.stringify({ kind, nonce: `${Date.now()}-${Math.random()}` })); } catch { /* Same-tab refresh still works without storage. */ }
}
export function subscribeMasterDataChange(listener: (kind: MasterDataKind) => void) {
  if (typeof window === "undefined") return () => {};
  const receive = (kind: unknown) => { if (kind === "products" || kind === "suppliers") listener(kind); };
  const local = (event: Event) => receive((event as CustomEvent).detail);
  const storage = (event: StorageEvent) => { if (event.key === storageKey && event.newValue) { try { receive(JSON.parse(event.newValue).kind); } catch { /* Ignore malformed cross-tab notifications. */ } } };
  window.addEventListener(eventName, local); window.addEventListener("storage", storage);
  return () => { window.removeEventListener(eventName, local); window.removeEventListener("storage", storage); };
}
export function isMasterDataQuery(key: readonly unknown[], kind: MasterDataKind) {
  const name = String(key[0] ?? "").toLowerCase();
  return kind === "suppliers" ? name.includes("supplier") : /product|item.*lookup|classification|pos-options/.test(name);
}

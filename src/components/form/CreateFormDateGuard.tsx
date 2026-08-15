import { useEffect } from "react";
import { nowLocal, todayLocal } from "@/utils/dateConstraints";

function createScope(input: HTMLInputElement): HTMLElement | null {
  return input.closest<HTMLElement>('[role="dialog"]') || input.closest<HTMLElement>("form") || input.closest<HTMLElement>("main");
}

function isCreateContext(input: HTMLInputElement) {
  if (input.dataset.allowPastDate === "true") return false;
  const scope = createScope(input);
  if (!scope) return false;
  const headings = Array.from(scope.querySelectorAll<HTMLElement>('h1,h2,h3,[role="heading"]'))
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean)
    .slice(0, 8)
    .join(" ");
  return /\b(create|new|register)\b/i.test(headings) && !/\bhistorical\s+import\b/i.test(headings);
}

function applyMinimum(input: HTMLInputElement) {
  if (!isCreateContext(input)) return;
  if (input.type === "date") input.min = todayLocal();
  if (input.type === "datetime-local") input.min = nowLocal();
}

function scan() {
  document.querySelectorAll<HTMLInputElement>('input[type="date"],input[type="datetime-local"]').forEach(applyMinimum);
}

export default function CreateFormDateGuard() {
  useEffect(() => {
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(document.body, { subtree: true, childList: true });
    const interval = window.setInterval(scan, 60_000);
    const onFocus = (event: FocusEvent) => {
      if (event.target instanceof HTMLInputElement && (event.target.type === "date" || event.target.type === "datetime-local")) applyMinimum(event.target);
    };
    document.addEventListener("focusin", onFocus);
    return () => {
      observer.disconnect();
      window.clearInterval(interval);
      document.removeEventListener("focusin", onFocus);
    };
  }, []);
  return null;
}

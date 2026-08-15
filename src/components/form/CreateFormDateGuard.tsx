import { useEffect } from "react";
import { nowLocal, todayLocal } from "@/utils/dateConstraints";

function createScope(node: Element): HTMLElement | null {
  return node.closest<HTMLElement>('[role="dialog"]') || node.closest<HTMLElement>("form") || node.closest<HTMLElement>("main");
}

function scopeHeadings(scope: HTMLElement) {
  return Array.from(scope.querySelectorAll<HTMLElement>('h1,h2,h3,[role="heading"]'))
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean)
    .slice(0, 8)
    .join(" ");
}

function isCreateScope(scope: HTMLElement) {
  const headings = scopeHeadings(scope);
  return /\b(create|new|register)\b/i.test(headings) && !/\bhistorical\s+import\b/i.test(headings);
}

function isGuardedInput(input: HTMLInputElement) {
  if (input.dataset.allowPastDate === "true") return false;
  const scope = createScope(input);
  return Boolean(scope && isCreateScope(scope));
}

function applyMinimum(input: HTMLInputElement) {
  if (!isGuardedInput(input)) return;
  if (input.type === "date") input.min = todayLocal();
  if (input.type === "datetime-local") input.min = nowLocal();
}

function scan() {
  document.querySelectorAll<HTMLInputElement>('input[type="date"],input[type="datetime-local"]').forEach(applyMinimum);
}

function validateAction(button: HTMLButtonElement) {
  const scope = createScope(button);
  if (!scope || !isCreateScope(scope)) return true;
  const text = button.textContent?.trim() ?? "";
  const isAction = button.type === "submit" || /\b(create|save|submit|register|post|add)\b/i.test(text);
  if (!isAction || /\bcancel\b/i.test(text)) return true;

  const inputs = Array.from(scope.querySelectorAll<HTMLInputElement>('input[type="date"],input[type="datetime-local"]'));
  for (const input of inputs) {
    applyMinimum(input);
    if (!isGuardedInput(input) || !input.value) continue;
    if (input.min && input.value < input.min) {
      input.setCustomValidity(input.type === "datetime-local" ? "Date/time cannot be before now." : "Date cannot be before today.");
      input.reportValidity();
      window.setTimeout(() => input.setCustomValidity(""), 0);
      return false;
    }
  }
  return true;
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
    const onClick = (event: MouseEvent) => {
      const button = event.target instanceof Element ? event.target.closest("button") : null;
      if (!(button instanceof HTMLButtonElement)) return;
      if (!validateAction(button)) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
      }
    };
    document.addEventListener("focusin", onFocus);
    document.addEventListener("click", onClick, true);
    return () => {
      observer.disconnect();
      window.clearInterval(interval);
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("click", onClick, true);
    };
  }, []);
  return null;
}

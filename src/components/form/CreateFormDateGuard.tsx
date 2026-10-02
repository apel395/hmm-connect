import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import useAuthStore from "@/store/auth";

type FiscalPeriod = {
  start_date: string;
  end_date: string;
  period_name: string;
  is_open: boolean;
  is_closed: boolean;
};

function createScope(node: Element): HTMLElement | null {
  return node.closest<HTMLElement>('[role="dialog"]') || node.closest<HTMLElement>("form") || node.closest<HTMLElement>("main");
}

function isCreateScope(scope: HTMLElement): boolean {
  const headings = Array.from(scope.querySelectorAll<HTMLElement>('h1,h2,h3,[role="heading"]'))
    .map((node) => node.textContent?.trim() ?? "")
    .slice(0, 8)
    .join(" ");
  return /\b(create|new|register|reclassify|edit)\b/i.test(headings);
}

function isAccountingDate(input: HTMLInputElement): boolean {
  if (input.dataset.accountingDate === "true") return true;
  const scope = createScope(input);
  if (!scope || !isCreateScope(scope)) return false;
  const label = input.closest("label")?.textContent ?? "";
  const text = `${input.name} ${input.id} ${label}`.toLowerCase();
  if (/\b(due|expiry|expiration|expected|delivery|tax invoice|faktur|birth|check.in|check.out)\b/.test(text)) return false;
  return /\b(posting|payment|invoice|voucher|journal|transaction|receipt|receiving|transfer|adjustment|purchase|acquisition|stock|document)\b/.test(text)
    && /\b(date|time|at)\b/.test(text);
}

function dateValue(input: HTMLInputElement) {
  return input.value.slice(0, 10);
}

function periodFor(value: string, periods: FiscalPeriod[]) {
  return periods.find((period) => period.start_date <= value && value <= period.end_date);
}

function validateInput(input: HTMLInputElement, periods: FiscalPeriod[]): boolean {
  if (!isAccountingDate(input) || !input.value) return true;
  const period = periodFor(dateValue(input), periods);
  if (period && period.is_open && !period.is_closed) {
    input.setCustomValidity("");
    return true;
  }
  input.setCustomValidity(period
    ? `Accounting period ${period.period_name} is closed. Reopen it before posting.`
    : "No accounting period covers this date.");
  input.reportValidity();
  return false;
}

function updateInput(input: HTMLInputElement, periods: FiscalPeriod[]) {
  if (!isAccountingDate(input)) return;
  const open = periods.filter((period) => period.is_open && !period.is_closed);
  if (open.length) {
    const openStart = open.map((period) => period.start_date).sort()[0];
    const start = input.dataset.minDate && input.dataset.minDate > openStart ? input.dataset.minDate : openStart;
    const end = open.map((period) => period.end_date).sort().at(-1)!;
    input.min = input.type === "datetime-local" ? `${start}T00:00` : start;
    input.max = input.type === "datetime-local" ? `${end}T23:59` : end;
  } else {
    input.removeAttribute("min");
    input.removeAttribute("max");
  }
  // The browser can show a continuous range. Validation above catches closed
  // months between separately opened accounting periods.
  if (input.value) {
    const period = periodFor(dateValue(input), periods);
    input.setCustomValidity(period?.is_open && !period.is_closed ? "" : period
      ? `Accounting period ${period.period_name} is closed. Reopen it before posting.`
      : "No accounting period covers this date.");
  }
}

export default function CreateFormDateGuard() {
  const authenticated = useAuthStore((state) => state.authenticated);
  const { data: periods } = useQuery({
    queryKey: ["accounting-period-date-guard"],
    queryFn: async () => (await api.get<FiscalPeriod[]>("/fiscal-periods")).data,
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: false,
    enabled: authenticated,
  });

  useEffect(() => {
    const scan = () => {
      if (!periods) return;
      document.querySelectorAll<HTMLInputElement>('input[type="date"],input[type="datetime-local"]')
        .forEach((input) => updateInput(input, periods));
    };
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(document.body, { subtree: true, childList: true });
    const onFocus = (event: FocusEvent) => {
      if (periods && event.target instanceof HTMLInputElement) updateInput(event.target, periods);
    };
    const onChange = (event: Event) => {
      if (periods && event.target instanceof HTMLInputElement && isAccountingDate(event.target)) {
        validateInput(event.target, periods);
      }
    };
    const validateScope = (target: Element): boolean => {
      if (!periods) return true; // The posting API remains authoritative.
      const scope = createScope(target);
      if (!scope) return true;
      for (const input of scope.querySelectorAll<HTMLInputElement>('input[type="date"],input[type="datetime-local"]')) {
        if (!validateInput(input, periods)) return false;
      }
      return true;
    };
    const onClick = (event: MouseEvent) => {
      const button = event.target instanceof Element ? event.target.closest("button") : null;
      if (!(button instanceof HTMLButtonElement)) return;
      const text = button.textContent?.trim() ?? "";
      if (button.type !== "submit" && !/\b(create|save|submit|verify|approve|post|add|correction)\b/i.test(text)) return;
      if (!validateScope(button)) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
      }
    };
    const onSubmit = (event: SubmitEvent) => {
      if (!validateScope(event.target as Element)) event.preventDefault();
    };
    document.addEventListener("focusin", onFocus);
    document.addEventListener("change", onChange, true);
    document.addEventListener("click", onClick, true);
    document.addEventListener("submit", onSubmit, true);
    return () => {
      observer.disconnect();
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("change", onChange, true);
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("submit", onSubmit, true);
    };
  }, [periods]);
  return null;
}

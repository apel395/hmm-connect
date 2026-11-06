export default function focusFormField(name: string) {
  window.requestAnimationFrame(() => {
    const field = document.querySelector(`[data-form-field="${name}"]`);
    if (!field) return;
    field.scrollIntoView({ behavior: "smooth", block: "center" });
    const control = field.querySelector<HTMLElement>(
      "input:not([type=hidden]), button, select, textarea",
    );
    control?.focus({ preventScroll: true });
  });
}

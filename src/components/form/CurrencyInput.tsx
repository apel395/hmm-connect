import { useEffect, useState } from "react";
import { FORM_UI } from "@/config/formUi";

interface Props {
  value: number;
  onValueChange: (value: number) => void;
  className?: string;
  disabled?: boolean;
  min?: number;
  placeholder?: string;
}

const formatCurrency = (value: number) =>
  Number.isFinite(value)
    ? value.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : "0.00";

export default function CurrencyInput({
  value,
  onValueChange,
  className = "",
  disabled,
  min = 0,
  placeholder,
}: Props) {
  const [focused, setFocused] = useState(false);
  const [display, setDisplay] = useState(value === 0 ? "0.00" : formatCurrency(value));

  useEffect(() => {
    if (!focused) setDisplay(formatCurrency(value));
  }, [value, focused]);

  const handleFocus = () => {
    setFocused(true);
    setDisplay(value === 0 ? "" : String(value));
  };

  const handleChange = (raw: string) => {
    const cleaned = raw.replace(/,/g, "").replace(/[^0-9.]/g, "");
    const parts = cleaned.split(".");
    const normalized = parts.length > 1
      ? `${parts[0]}.${parts.slice(1).join("").slice(0, 2)}`
      : parts[0];

    setDisplay(normalized);
    const numeric = normalized === "" || normalized === "." ? 0 : Number(normalized);
    onValueChange(Number.isFinite(numeric) ? Math.max(min, numeric) : 0);
  };

  const handleBlur = () => {
    setFocused(false);
    setDisplay(formatCurrency(value));
  };

  return (
    <input
      type="text"
      inputMode="decimal"
      value={display}
      disabled={disabled}
      placeholder={placeholder}
      onFocus={handleFocus}
      onChange={(event) => handleChange(event.target.value)}
      onBlur={handleBlur}
      data-form-control
      data-form-density="compact"
      className={`${FORM_UI.controlBase} ${FORM_UI.density.compact.control} text-right tabular-nums ${className}`}
    />
  );
}

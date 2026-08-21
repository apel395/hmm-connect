import { useEffect, useState } from "react";
import { FORM_UI } from "@/config/formUi";

interface Props {
  value: number;
  onValueChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
  disabled?: boolean;
}

export default function QuantityInput({
  value,
  onValueChange,
  min = 0,
  max,
  step = 0.01,
  className = "",
  disabled,
}: Props) {
  const [text, setText] = useState(value > 0 ? String(value) : "");
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setText(value > 0 ? String(value) : "");
  }, [value, focused]);

  return (
    <input
      type="text"
      inputMode="decimal"
      disabled={disabled}
      value={text}
      placeholder="0.00"
      data-form-control
      data-form-density="compact"
      className={`${FORM_UI.controlBase} ${FORM_UI.density.compact.control} text-right tabular-nums ${className}`}
      onFocus={() => {
        setFocused(true);
        if (Number(text) === 0) setText("");
      }}
      onChange={(event) => {
        let next = event.target.value.replace(/[^0-9.]/g, "");
        const parts = next.split(".");
        if (parts.length > 2) next = `${parts[0]}.${parts.slice(1).join("")}`;
        next = next.replace(/^0+(?=\d)/, "");
        setText(next);

        const parsed = Number(next);
        if (next === "" || next === "." || Number.isNaN(parsed)) {
          onValueChange(0);
          return;
        }
        const bounded = Math.max(min, max === undefined ? parsed : Math.min(max, parsed));
        onValueChange(bounded);
      }}
      onBlur={() => {
        setFocused(false);
        const parsed = Number(text);
        if (!text || Number.isNaN(parsed)) {
          setText("");
          onValueChange(0);
          return;
        }
        const bounded = Math.max(min, max === undefined ? parsed : Math.min(max, parsed));
        onValueChange(bounded);
        const decimals = String(step).includes(".") ? String(step).split(".")[1].length : 0;
        setText(decimals > 0 ? bounded.toFixed(decimals) : String(bounded));
      }}
    />
  );
}

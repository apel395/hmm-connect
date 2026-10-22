import { forwardRef, useEffect, useState } from "react";
import Input, { type InputProps } from "@/components/ui/Input";

const displayNumber = (value: InputProps["value"]) => Number(value || 0) === 0 ? "" : String(value);

// Keep the editable text separate from the numeric Item Master value. An empty
// optional amount represents zero without forcing a leading 0 back while typing.
const ItemNumberInput = forwardRef<HTMLInputElement, InputProps>(
  ({ value, placeholder = "0", onChange, onFocus, onBlur, ...props }, ref) => {
    const [draft, setDraft] = useState(() => displayNumber(value));
    useEffect(() => {
      setDraft(current => Number(current || 0) === Number(value || 0) ? current : displayNumber(value));
    }, [value]);
    return <Input {...props} ref={ref} type="number" value={draft} placeholder={placeholder}
      data-item-number
      onFocus={event => {
        if (Number(event.currentTarget.value || 0) === 0) {
          event.currentTarget.value = "";
          setDraft("");
        }
        onFocus?.(event);
      }}
      onChange={event => {
        const normalized = event.currentTarget.value.replace(/^0+(?=\d)/, "");
        event.currentTarget.value = normalized;
        setDraft(normalized);
        onChange?.(event);
      }}
      onBlur={event => {
        if (Number(event.currentTarget.value || 0) === 0) setDraft("");
        onBlur?.(event);
      }} />;
  },
);
ItemNumberInput.displayName = "ItemNumberInput";
export default ItemNumberInput;

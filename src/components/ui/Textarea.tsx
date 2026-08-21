import { forwardRef, TextareaHTMLAttributes } from "react";
import clsx from "clsx";
import { FORM_UI, type FormDensity } from "@/config/formUi";

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
  density?: FormDensity;
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className,
      error = false,
      density = FORM_UI.defaultDensity,
      disabled,
      rows = 4,
      ...props
    },
    ref,
  ) => {
    return (
      <textarea
        ref={ref}
        rows={rows}
        disabled={disabled}
        data-form-control
        data-form-density={density}
        aria-invalid={error || undefined}
        className={clsx(
          "flex resize-y",
          FORM_UI.controlBase,
          FORM_UI.density[density].textarea,
          error && FORM_UI.error,
          className,
        )}
        {...props}
      />
    );
  },
);

Textarea.displayName = "Textarea";

export default Textarea;

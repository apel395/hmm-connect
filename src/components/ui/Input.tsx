import { forwardRef, InputHTMLAttributes } from "react";
import clsx from "clsx";
import { FORM_UI, type FormDensity } from "@/config/formUi";

export interface InputProps
  extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  density?: FormDensity;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      error = false,
      density = FORM_UI.defaultDensity,
      disabled,
      ...props
    },
    ref,
  ) => {
    return (
      <input
        ref={ref}
        disabled={disabled}
        data-form-control
        data-form-density={density}
        aria-invalid={error || undefined}
        className={clsx(
          "flex",
          FORM_UI.controlBase,
          FORM_UI.density[density].control,
          error && FORM_UI.error,
          className,
        )}
        {...props}
      />
    );
  },
);

Input.displayName = "Input";

export default Input;

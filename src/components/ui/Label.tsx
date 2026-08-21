import { forwardRef, LabelHTMLAttributes } from "react";
import clsx from "clsx";
import { FORM_UI, type FormDensity } from "@/config/formUi";

export interface LabelProps
  extends LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean;
  density?: FormDensity;
}

const Label = forwardRef<HTMLLabelElement, LabelProps>(
  (
    {
      className,
      required = false,
      density = FORM_UI.defaultDensity,
      children,
      ...props
    },
    ref,
  ) => {
    return (
      <label
        ref={ref}
        data-form-label
        className={clsx(
          FORM_UI.label,
          FORM_UI.density[density].label,
          className,
        )}
        {...props}
      >
        <span>{children}</span>
        {required && (
          <>
            <span className="text-red-500" aria-hidden="true">*</span>
            <span className="sr-only">(required)</span>
          </>
        )}
      </label>
    );
  },
);

Label.displayName = "Label";

export default Label;

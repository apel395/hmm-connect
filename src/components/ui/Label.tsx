import { forwardRef, LabelHTMLAttributes } from "react";
import clsx from "clsx";

export interface LabelProps
  extends LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean;
}

const Label = forwardRef<HTMLLabelElement, LabelProps>(
  (
    {
      className,
      required = false,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <label
        ref={ref}
        className={clsx(
          "mb-2 inline-flex items-center gap-1 text-sm font-medium text-slate-700",
          className
        )}
        {...props}
      >
        <span>{children}</span>

        {required && (
          <span
            className="text-red-500"
            aria-hidden="true"
          >
            *
          </span>
        )}
      </label>
    );
  }
);

Label.displayName = "Label";

export default Label;

import type { ReactNode } from "react";

interface FormFieldProps {
  label: string;
  children: ReactNode;
  required?: boolean;
  help?: string;
  error?: string;
  htmlFor?: string;
}

export default function FormField({
  label,
  children,
  required,
  help,
  error,
  htmlFor,
}: FormFieldProps) {
  return (
    <div className="min-w-0 space-y-1">
      <label
        htmlFor={htmlFor}
        className="block text-xs font-medium text-slate-700"
      >
        {label}{" "}
        {required && (
          <span className="text-red-600" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      ) : help ? (
        <p className="text-xs text-slate-500">{help}</p>
      ) : null}
    </div>
  );
}

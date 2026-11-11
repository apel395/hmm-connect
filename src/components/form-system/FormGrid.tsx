import type { ReactNode } from "react";
import clsx from "clsx";

interface FormGridProps {
  children: ReactNode;
  columns?: 2 | 3;
  className?: string;
}

export default function FormGrid({
  children,
  columns = 2,
  className,
}: FormGridProps) {
  return (
    <div
      className={clsx(
        "grid grid-cols-1 gap-3",
        columns === 2 ? "md:grid-cols-2" : "md:grid-cols-3",
        className,
      )}
    >
      {children}
    </div>
  );
}

import { HTMLAttributes } from "react";
import clsx from "clsx";

export interface DividerProps
  extends HTMLAttributes<HTMLHRElement> {
  orientation?: "horizontal" | "vertical";
}

export default function Divider({
  orientation = "horizontal",
  className,
  ...props
}: DividerProps) {
  if (orientation === "vertical") {
    return (
      <div
        role="separator"
        aria-orientation="vertical"
        className={clsx(
          "mx-2 h-full w-px shrink-0 bg-slate-200",
          className
        )}
        {...props}
      />
    );
  }

  return (
    <hr
      role="separator"
      aria-orientation="horizontal"
      className={clsx(
        "my-4 w-full border-0 border-t border-slate-200",
        className
      )}
      {...props}
    />
  );
}

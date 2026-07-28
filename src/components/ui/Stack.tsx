import { HTMLAttributes } from "react";
import clsx from "clsx";

export interface StackProps
  extends HTMLAttributes<HTMLDivElement> {
  direction?: "vertical" | "horizontal";
  spacing?: 0 | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12;
  align?: "start" | "center" | "end" | "stretch";
  justify?:
    | "start"
    | "center"
    | "end"
    | "between"
    | "around"
    | "evenly";
  wrap?: boolean;
}

const spacingMap = {
  0: "gap-0",
  1: "gap-1",
  2: "gap-2",
  3: "gap-3",
  4: "gap-4",
  5: "gap-5",
  6: "gap-6",
  8: "gap-8",
  10: "gap-10",
  12: "gap-12",
};

const alignMap = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
  stretch: "items-stretch",
};

const justifyMap = {
  start: "justify-start",
  center: "justify-center",
  end: "justify-end",
  between: "justify-between",
  around: "justify-around",
  evenly: "justify-evenly",
};

export default function Stack({
  direction = "vertical",
  spacing = 4,
  align = "stretch",
  justify = "start",
  wrap = false,
  className,
  children,
  ...props
}: StackProps) {
  return (
    <div
      className={clsx(
        "flex",
        direction === "vertical" ? "flex-col" : "flex-row",
        spacingMap[spacing],
        alignMap[align],
        justifyMap[justify],
        wrap && "flex-wrap",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

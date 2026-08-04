import { HTMLAttributes } from "react";
import clsx from "clsx";

export interface ContainerProps
  extends HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "md" | "lg" | "xl" | "full";
}

const sizes = {
  sm: "max-w-3xl",
  md: "max-w-5xl",
  lg: "max-w-6xl",
  xl: "max-w-7xl",
  full: "max-w-full",
};

export default function Container({
  size = "xl",
  className,
  children,
  ...props
}: ContainerProps) {
  return (
    <div
      className={clsx(
        "mx-auto w-full px-3 sm:px-4 lg:px-5",
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

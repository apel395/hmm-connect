import { HTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({
  children,
  className,
  ...props
}: CardProps) {
  return (
    <div
      className={clsx(
        "rounded-xl border border-slate-200 bg-white shadow-sm",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export type CardHeaderProps = HTMLAttributes<HTMLDivElement>;

export function CardHeader({
  className,
  ...props
}: CardHeaderProps) {
  return (
    <div
      className={clsx(
        "flex items-center justify-between border-b border-slate-200 px-6 py-4",
        className
      )}
      {...props}
    />
  );
}

export type CardTitleProps = HTMLAttributes<HTMLHeadingElement>;

export function CardTitle({
  className,
  ...props
}: CardTitleProps) {
  return (
    <h2
      className={clsx(
        "text-lg font-semibold text-slate-900",
        className
      )}
      {...props}
    />
  );
}

export type CardDescriptionProps = HTMLAttributes<HTMLParagraphElement>;

export function CardDescription({
  className,
  ...props
}: CardDescriptionProps) {
  return (
    <p
      className={clsx(
        "mt-1 text-sm text-slate-500",
        className
      )}
      {...props}
    />
  );
}

export type CardContentProps = HTMLAttributes<HTMLDivElement>;

export function CardContent({
  className,
  ...props
}: CardContentProps) {
  return (
    <div
      className={clsx(
        "p-6",
        className
      )}
      {...props}
    />
  );
}

export type CardFooterProps = HTMLAttributes<HTMLDivElement>;

export function CardFooter({
  className,
  ...props
}: CardFooterProps) {
  return (
    <div
      className={clsx(
        "flex items-center justify-end gap-2 border-t border-slate-200 px-6 py-4",
        className
      )}
      {...props}
    />
  );
}

export default Card;

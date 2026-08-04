import {
  HTMLAttributes,
  TableHTMLAttributes,
  TdHTMLAttributes,
  ThHTMLAttributes,
} from "react";
import clsx from "clsx";

export interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  variant?: "standard" | "grid";
  stickyHeader?: boolean;
}

export function Table({
  className,
  children,
  variant = "standard",
  stickyHeader = false,
  ...props
}: TableProps) {
  return (
    <div className="w-full overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table
        className={clsx(
          "min-w-full text-[13px]",
          variant === "grid" ? "table-grid" : "table-standard",
          stickyHeader && "table-sticky-header",
          className
        )}
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

export type THeadProps = HTMLAttributes<HTMLTableSectionElement>;

export function THead({
  className,
  children,
  ...props
}: THeadProps) {
  return (
    <thead
      className={clsx("bg-slate-50", className)}
      {...props}
    >
      {children}
    </thead>
  );
}

export type TBodyProps = HTMLAttributes<HTMLTableSectionElement>;

export function TBody({
  className,
  children,
  ...props
}: TBodyProps) {
  return (
    <tbody
      className={clsx("divide-y divide-slate-100", className)}
      {...props}
    >
      {children}
    </tbody>
  );
}

export type TFootProps = HTMLAttributes<HTMLTableSectionElement>;

export function TFoot({
  className,
  children,
  ...props
}: TFootProps) {
  return (
    <tfoot
      className={clsx("bg-slate-50", className)}
      {...props}
    >
      {children}
    </tfoot>
  );
}

export type TRProps = HTMLAttributes<HTMLTableRowElement>;

export function TR({
  className,
  children,
  ...props
}: TRProps) {
  return (
    <tr
      className={clsx(
        "transition-colors hover:bg-slate-50 aria-selected:bg-blue-50 data-[state=selected]:bg-blue-50",
        className
      )}
      {...props}
    >
      {children}
    </tr>
  );
}

export type THProps = ThHTMLAttributes<HTMLTableCellElement>;

export function TH({
  className,
  children,
  ...props
}: THProps) {
  return (
    <th
      className={clsx(
        "h-9 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-600",
        className
      )}
      {...props}
    >
      {children}
    </th>
  );
}

export type TDProps = TdHTMLAttributes<HTMLTableCellElement>;

export function TD({
  className,
  children,
  ...props
}: TDProps) {
  return (
    <td
      className={clsx(
        "h-10 px-3 py-2 align-middle text-slate-700",
        className
      )}
      {...props}
    >
      {children}
    </td>
  );
}

/* Optional aliases for compatibility */

export const TableHead = THead;
export const TableBody = TBody;
export const TableFooter = TFoot;
export const TableRow = TR;
export const TableCell = TD;
export const TableHeader = TH;

export default Table;

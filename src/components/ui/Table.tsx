import {
  HTMLAttributes,
  TableHTMLAttributes,
  TdHTMLAttributes,
  ThHTMLAttributes,
} from "react";
import clsx from "clsx";

export type TableProps = TableHTMLAttributes<HTMLTableElement>;

export function Table({
  className,
  children,
  ...props
}: TableProps) {
  return (
    <div className="w-full overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table
        className={clsx(
          "min-w-full border-collapse text-sm",
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
        "border-b border-slate-100 transition-colors hover:bg-slate-50",
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
        "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600",
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
        "px-4 py-3 align-middle text-slate-700",
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
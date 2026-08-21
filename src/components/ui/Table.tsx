import {
  createContext,
  HTMLAttributes,
  TableHTMLAttributes,
  TdHTMLAttributes,
  ThHTMLAttributes,
  type ReactNode,
  useContext,
} from "react";
import clsx from "clsx";
import { TABLE_UI, type TableDensity } from "@/config/tableUi";

const TableDensityContext = createContext<TableDensity>(TABLE_UI.defaultDensity);

export interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  variant?: "standard" | "grid";
  stickyHeader?: boolean;
  density?: TableDensity;
  containerClassName?: string;
}

export function Table({
  className,
  containerClassName,
  children,
  variant = "standard",
  stickyHeader = false,
  density = TABLE_UI.defaultDensity,
  ...props
}: TableProps) {
  return (
    <TableDensityContext.Provider value={density}>
      <div className={clsx("w-full overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm", containerClassName)}>
        <table
          data-table-density={density}
          className={clsx(
            "min-w-full",
            TABLE_UI.density[density].table,
            variant === "grid" ? "table-grid" : "table-standard",
            stickyHeader && "table-sticky-header",
            className,
          )}
          {...props}
        >
          {children}
        </table>
      </div>
    </TableDensityContext.Provider>
  );
}

export type THeadProps = HTMLAttributes<HTMLTableSectionElement>;

export function THead({ className, children, ...props }: THeadProps) {
  return <thead className={clsx("bg-slate-50", className)} {...props}>{children}</thead>;
}

export type TBodyProps = HTMLAttributes<HTMLTableSectionElement>;

export function TBody({ className, children, ...props }: TBodyProps) {
  return <tbody className={clsx("divide-y divide-slate-100", className)} {...props}>{children}</tbody>;
}

export type TFootProps = HTMLAttributes<HTMLTableSectionElement>;

export function TFoot({ className, children, ...props }: TFootProps) {
  return <tfoot className={clsx("bg-slate-50", className)} {...props}>{children}</tfoot>;
}

export type TRProps = HTMLAttributes<HTMLTableRowElement>;

export function TR({ className, children, ...props }: TRProps) {
  return (
    <tr
      className={clsx(
        "transition-colors hover:bg-slate-50 aria-selected:bg-blue-50 data-[state=selected]:bg-blue-50",
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  );
}

export interface THProps extends ThHTMLAttributes<HTMLTableCellElement> {
  numeric?: boolean;
}

export function TH({ className, children, numeric = false, ...props }: THProps) {
  const density = useContext(TableDensityContext);
  return (
    <th
      className={clsx(
        TABLE_UI.density[density].headerCell,
        TABLE_UI.header,
        numeric ? TABLE_UI.numeric : "text-left",
        className,
      )}
      {...props}
    >
      {children}
    </th>
  );
}

export interface TDProps extends TdHTMLAttributes<HTMLTableCellElement> {
  numeric?: boolean;
}

export function TD({ className, children, numeric = false, ...props }: TDProps) {
  const density = useContext(TableDensityContext);
  return (
    <td
      className={clsx(
        TABLE_UI.density[density].bodyCell,
        "align-middle text-slate-700",
        numeric && TABLE_UI.numeric,
        className,
      )}
      {...props}
    >
      {children}
    </td>
  );
}

export function TableCellStack({
  primary,
  secondary,
  className,
}: {
  primary: ReactNode;
  secondary?: ReactNode;
  className?: string;
}) {
  return (
    <span className={clsx("block min-w-0", className)}>
      <span className="block truncate font-medium text-slate-800">{primary}</span>
      {secondary ? <span className={clsx("block truncate", TABLE_UI.secondaryText)}>{secondary}</span> : null}
    </span>
  );
}

export const TableHead = THead;
export const TableBody = TBody;
export const TableFooter = TFoot;
export const TableRow = TR;
export const TableCell = TD;
export const TableHeader = TH;

export default Table;

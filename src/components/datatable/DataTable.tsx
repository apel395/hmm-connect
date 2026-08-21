import type { ReactNode } from "react";
import {
  Table,
  THead,
  TBody,
  TR,
  TH,
  TD,
} from "@/components/ui/Table";
import type { TableDensity } from "@/config/tableUi";

export interface DataTableColumn<Row> {
  key: string;
  title: string;
  render?: (row: Row) => ReactNode;
  numeric?: boolean;
  className?: string;
  headerClassName?: string;
}

interface DataTableProps<Row> {
  columns: DataTableColumn<Row>[];
  rows: Row[];
  density?: TableDensity;
  stickyHeader?: boolean;
  variant?: "standard" | "grid";
  className?: string;
  getRowKey?: (row: Row, index: number) => string | number;
}

export default function DataTable<Row extends Record<string, unknown>>({
  columns,
  rows,
  density,
  stickyHeader = false,
  variant = "standard",
  className,
  getRowKey,
}: DataTableProps<Row>) {
  return (
    <Table density={density} stickyHeader={stickyHeader} variant={variant} className={className}>
      <THead>
        <TR>
          {columns.map((column) => (
            <TH key={column.key} numeric={column.numeric} className={column.headerClassName}>
              {column.title}
            </TH>
          ))}
        </TR>
      </THead>
      <TBody>
        {rows.map((row, index) => (
          <TR key={getRowKey ? getRowKey(row, index) : index}>
            {columns.map((column) => (
              <TD key={column.key} numeric={column.numeric} className={column.className}>
                {column.render ? column.render(row) : (row[column.key] as ReactNode)}
              </TD>
            ))}
          </TR>
        ))}
      </TBody>
    </Table>
  );
}

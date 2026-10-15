export type StockColumn =
  "warehouse" | "quantity" | "uom" | "cost" | "value" | "status";
export const STOCK_COLUMNS: {
  id: StockColumn;
  label: string;
  width: number;
}[] = [
  { id: "warehouse", label: "Warehouse", width: 180 },
  { id: "quantity", label: "On hand", width: 96 },
  { id: "uom", label: "Unit", width: 56 },
  { id: "cost", label: "Average cost", width: 125 },
  { id: "value", label: "Stock value", width: 145 },
  { id: "status", label: "Stock status", width: 100 },
];

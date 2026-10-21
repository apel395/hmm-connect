import { printNumber, type InventoryPrintReport } from "@/utils/inventoryPrint";

export type ExpectedReceivingItem = {
  product_code?: string | null; product_name?: string | null; uom?: string | null;
  ordered_quantity: string | number; received_quantity?: string | number | null;
  remaining_quantity: string | number;
};
export type ExpectedReceivingOrder = {
  id: number; po_number: string; expected_date?: string | null;
  supplier_name?: string | null; location_name?: string | null;
  department_name?: string | null; items: ExpectedReceivingItem[];
};
export type ExpectedReceivingFilters = { date_from?: string; date_to?: string };

export function filterExpectedReceiving(orders: ExpectedReceivingOrder[], filters: ExpectedReceivingFilters) {
  return orders.filter(order => (!filters.date_from || Boolean(order.expected_date && order.expected_date >= filters.date_from)) &&
    (!filters.date_to || Boolean(order.expected_date && order.expected_date <= filters.date_to)));
}

export function expectedReceivingReport(orders: ExpectedReceivingOrder[], filters: ExpectedReceivingFilters = {}, orderId?: number): InventoryPrintReport {
  if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) throw new Error("From date must not exceed To date");
  const selected = filterExpectedReceiving(orders, filters).filter(order => orderId == null || order.id === orderId)
    .map(order => ({...order, items: order.items.filter(item => Number(item.remaining_quantity) > 0)}))
    .filter(order => order.items.length > 0);
  if (orderId != null && selected.length !== 1) throw new Error("This PO no longer has outstanding items in the selected dates. Refresh Expected deliveries.");
  const rowCount = selected.reduce((count, order) => count + order.items.length, 0);
  return {
    title: "Expected Receiving",
    context: `Delivery dates: ${filters.date_from || "All"} to ${filters.date_to || "All"}`,
    summary: `${selected.length} purchase order${selected.length === 1 ? "" : "s"} · ${rowCount} outstanding item line${rowCount === 1 ? "" : "s"}`,
    rowCount,
    columns: [{label:"Item code",code:true},{label:"Description"},{label:"Ordered",numeric:true},
      {label:"Received",numeric:true},{label:"Remaining",numeric:true},{label:"UOM"}],
    groups: selected.map(order => ({
      title: `${order.po_number} · ${order.supplier_name || "—"}`,
      detail: `Expected: ${order.expected_date || "Unscheduled"} · Location: ${order.location_name || "—"} · Department: ${order.department_name || "—"}`,
      rows: order.items.map(item => [item.product_code,item.product_name,printNumber(item.ordered_quantity),printNumber(item.received_quantity),printNumber(item.remaining_quantity),item.uom]),
    })),
  };
}

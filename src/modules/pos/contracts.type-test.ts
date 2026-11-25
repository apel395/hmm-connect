/**
 * Type-only regression checks for POS API contracts. Included by `tsc -b`;
 * never imported by the app. `@ts-expect-error` lines fail if a contract is
 * weakened back to `any` or an invalid status/option slips through.
 */
import type { PosPaymentMethod, PosStatusFilter } from "./api";
import type { OutletReport, OrderMode } from "./operationsApi";
import type { PosChoice, PosPage, PosProduct, PosSale, PosSalesPage, PosStatus } from "./types";

declare const page: PosPage<PosProduct>;
const productId: number = page.items[0]?.product_id ?? 0;
// @ts-expect-error page metadata is numeric, not an arbitrary string
const invalidPageSize: string = page.page_size;

declare const sale: PosSale;
const saleStatus: PosStatus = sale.status;
// @ts-expect-error POS statuses are backend-defined
const invalidStatus: PosStatus = "APPROVED";

declare const filter: PosStatusFilter;
const validFilter: PosStatusFilter = "ALL";
// @ts-expect-error unknown statuses cannot be sent as list filters
const invalidFilter: PosStatusFilter = "ARCHIVED";

declare const payment: PosPaymentMethod;
const validPayment: PosPaymentMethod = "BANK_TRANSFER";
// @ts-expect-error payment methods are enumerated
const invalidPayment: PosPaymentMethod = "CASH_ON_DELIVERY";

declare const mode: OrderMode;
const validMode: OrderMode = "EVENT";
// @ts-expect-error outlet order modes are enumerated
const invalidMode: OrderMode = "QUEUE";

declare const salesPage: PosSalesPage;
const postedValue = salesPage.summary.posted_value;
// @ts-expect-error summary counts are numeric
const invalidCount: string = salesPage.summary.posted_count;

declare const choice: PosChoice;
const choiceName: string = choice.name;

declare const report: OutletReport;
const dailyDate: string = report.daily[0]?.date ?? "";
// @ts-expect-error report payment totals are keyed by method
const invalidPaymentKey: string = report.payments.CHEQUE;

void [
  productId,
  invalidPageSize,
  saleStatus,
  invalidStatus,
  filter,
  validFilter,
  invalidFilter,
  payment,
  validPayment,
  invalidPayment,
  mode,
  validMode,
  invalidMode,
  postedValue,
  invalidCount,
  choiceName,
  dailyDate,
  invalidPaymentKey,
];

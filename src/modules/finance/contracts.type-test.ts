/**
 * Type-only regression checks for finance API contracts.
 *
 * This file is included by `tsc -b` but never imported by the app. The
 * `@ts-expect-error` lines fail the build if a shared contract is weakened.
 */
import type { APStatus } from "./accounts-payable/reportingApi";
import type { InvoiceAction } from "./supplier-invoices/api";
import type { PaymentAction } from "./payments/api";
import type { Voucher, VoucherListParams, VoucherStatus } from "./payment-vouchers/api";
import type {
  FinanceAllowedActions,
  FinancePage,
  RawPaymentStatus,
  ReportedPaymentStatus,
} from "./types";

declare const page: FinancePage<{ id: number }>;
const firstId: number | undefined = page.items[0]?.id;

declare const apStatus: APStatus;
const validApStatus: APStatus = "PARTIALLY_PAID";
// @ts-expect-error raw backend PARTIAL is not a reported AP status
const invalidApStatus: APStatus = "PARTIAL";

declare const rawStatus: RawPaymentStatus;
const validRawStatus: RawPaymentStatus = "PARTIAL";

declare const reportedStatus: ReportedPaymentStatus;
const validReportedStatus: ReportedPaymentStatus = "PARTIALLY_PAID";
// @ts-expect-error raw PARTIAL must be normalized before display
const invalidReportedStatus: ReportedPaymentStatus = "PARTIAL";

declare const actions: FinanceAllowedActions;
const canApprove: boolean | undefined = actions.can_approve;
// @ts-expect-error capability flags are booleans, never strings
const invalidActions: FinanceAllowedActions = { can_approve: "yes" };

declare const invoiceActionValue: InvoiceAction;
const validInvoiceAction: InvoiceAction = "generate-journal";
// @ts-expect-error posting is not a supplier invoice action
const invalidInvoiceAction: InvoiceAction = "post";

declare const paymentActionValue: PaymentAction;
const validPaymentAction: PaymentAction = "approve";
// @ts-expect-error voucher approval is not a payment action
const invalidPaymentAction: PaymentAction = "approve-voucher";

declare const voucher: Voucher;
const voucherStatus: VoucherStatus = voucher.status;
// @ts-expect-error voucher states are backend-defined
const invalidVoucherStatus: VoucherStatus = "ARCHIVED";

declare const voucherParams: VoucherListParams;
const voucherPage: number | undefined = voucherParams.page;

void [
  firstId,
  apStatus,
  validApStatus,
  invalidApStatus,
  rawStatus,
  validRawStatus,
  reportedStatus,
  validReportedStatus,
  invalidReportedStatus,
  actions,
  canApprove,
  invalidActions,
  invoiceActionValue,
  validInvoiceAction,
  invalidInvoiceAction,
  paymentActionValue,
  validPaymentAction,
  invalidPaymentAction,
  voucher,
  voucherStatus,
  invalidVoucherStatus,
  voucherParams,
  voucherPage,
];

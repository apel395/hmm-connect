import { Link } from "react-router-dom";
import { Fragment } from "react";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
const money = (value: any) =>
  Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
export default function FinancialStatementTable({
  sections,
  comparative,
  mode = "comparative",
  ledgerUrl,
}: {
  sections: any[];
  comparative?: boolean;
  mode?: "comparative" | "opening_closing";
  ledgerUrl: (id: number) => string;
}) {
  const numeric = "whitespace-nowrap text-right tabular-nums";
  const yearly = mode === "opening_closing";
  const rowValue = (row: any, key: any, fallbackKey?: any) =>
    yearly ? row[fallbackKey ?? key] ?? row[key] ?? 0 : row[key] ?? 0;
  return (
    <Table variant="grid" stickyHeader className="min-w-[850px]">
      <THead>
        <TR>
          <TH>Account</TH>
          {yearly ? (
            <>
              <TH className={numeric}>Opening Amount</TH>
              <TH className={numeric}>Closing Amount</TH>
            </>
          ) : (
            <>
              <TH className={numeric}>Current Amount</TH>
              {comparative && (
                <>
                  <TH className={numeric}>Comparative Amount</TH>
                  <TH className={numeric}>Variance</TH>
                  <TH className={numeric}>Variance %</TH>
                </>
              )}
            </>
          )}
        </TR>
      </THead>
      <TBody>
        {sections.map((section) => (
          <Fragment key={section.code}>
            {
              <TR key={section.code} className="bg-slate-100 font-bold">
                <TD>{section.label}</TD>
                {yearly ? (
                  <>
                    <TD className={numeric}>{money(rowValue(section, "opening_total", "opening_amount"))}</TD>
                    <TD className={numeric}>{money(rowValue(section, "closing_total", "closing_amount"))}</TD>
                  </>
                ) : (
                  <>
                    <TD className={numeric}>{money(rowValue(section, "total"))}</TD>
                    {comparative && (
                      <>
                        <TD className={numeric}>{money(rowValue(section, "comparative_total"))}</TD>
                        <TD className={numeric}>{money(rowValue(section, "variance_amount"))}</TD>
                        <TD className={numeric}>
                          {section.variance_percentage == null
                            ? "—"
                            : `${money(section.variance_percentage)}%`}
                        </TD>
                      </>
                    )}
                  </>
                )}
              </TR>
            }
            {section.groups.map((group: any) => (
              <Fragment key={`${section.code}-${group.code}`}>
                <TR
                  key={`${section.code}-${group.code}`}
                  className="bg-slate-50 font-semibold"
                >
                  <TD className="pl-6">{group.label}</TD>
                  {yearly ? (
                    <>
                      <TD className={numeric}>{money(rowValue(group, "opening_total", "opening_amount"))}</TD>
                      <TD className={numeric}>{money(rowValue(group, "closing_total", "closing_amount"))}</TD>
                    </>
                  ) : (
                    <>
                      <TD className={numeric}>{money(rowValue(group, "total"))}</TD>
                      {comparative && (
                        <>
                          <TD className={numeric}>{money(rowValue(group, "comparative_total"))}</TD>
                          <TD className={numeric}>{money(rowValue(group, "variance_amount"))}</TD>
                          <TD className={numeric}>
                            {group.variance_percentage == null
                              ? "—"
                              : `${money(group.variance_percentage)}%`}
                          </TD>
                        </>
                      )}
                    </>
                  )}
                </TR>
                {group.accounts.map((account: any) => (
                  <TR
                    key={`${group.code}-${account.account_id ?? account.account_name}`}
                  >
                    <TD className="pl-10">
                      {account.account_id ? (
                        <Link
                          className="text-emerald-700 hover:underline"
                          to={ledgerUrl(account.account_id)}
                        >
                          {account.account_code} — {account.account_name}
                        </Link>
                      ) : (
                        account.account_name
                      )}
                    </TD>
                    {yearly ? (
                      <>
                        <TD className={numeric}>{money(account.opening_amount)}</TD>
                        <TD className={numeric}>{money(account.closing_amount)}</TD>
                      </>
                    ) : (
                      <>
                        <TD className={numeric}>{money(account.current_amount)}</TD>
                        {comparative && (
                          <>
                            <TD className={numeric}>{money(account.comparative_amount)}</TD>
                            <TD className={numeric}>{money(account.variance_amount)}</TD>
                            <TD className={numeric}>
                              {account.variance_percentage == null
                                ? "—"
                                : `${money(account.variance_percentage)}%`}
                            </TD>
                          </>
                        )}
                      </>
                    )}
                  </TR>
                ))}
              </Fragment>
            ))}
          </Fragment>
        ))}
      </TBody>
    </Table>
  );
}

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
  ledgerUrl,
}: {
  sections: any[];
  comparative: boolean;
  ledgerUrl: (id: number) => string;
}) {
  const numeric = "whitespace-nowrap text-right tabular-nums";
  return (
    <Table variant="grid" stickyHeader className="min-w-[850px]">
      <THead>
        <TR>
          <TH>Account</TH>
          <TH className={numeric}>Current Amount</TH>
          {comparative && (
            <>
              <TH className={numeric}>Comparative Amount</TH>
              <TH className={numeric}>Variance</TH>
              <TH className={numeric}>Variance %</TH>
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
                <TD className={numeric}>{money(section.total)}</TD>
                {comparative && (
                  <>
                    <TD className={numeric}>
                      {money(section.comparative_total)}
                    </TD>
                    <TD className={numeric}>
                      {money(section.variance_amount)}
                    </TD>
                    <TD className={numeric}>
                      {section.variance_percentage == null
                        ? "—"
                        : `${money(section.variance_percentage)}%`}
                    </TD>
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
                  <TD className={numeric}>{money(group.total)}</TD>
                  {comparative && (
                    <>
                      <TD className={numeric}>
                        {money(group.comparative_total)}
                      </TD>
                      <TD className={numeric}>
                        {money(group.variance_amount)}
                      </TD>
                      <TD className={numeric}>
                        {group.variance_percentage == null
                          ? "—"
                          : `${money(group.variance_percentage)}%`}
                      </TD>
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
                    <TD className={numeric}>{money(account.current_amount)}</TD>
                    {comparative && (
                      <>
                        <TD className={numeric}>
                          {money(account.comparative_amount)}
                        </TD>
                        <TD className={numeric}>
                          {money(account.variance_amount)}
                        </TD>
                        <TD className={numeric}>
                          {account.variance_percentage == null
                            ? "—"
                            : `${money(account.variance_percentage)}%`}
                        </TD>
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

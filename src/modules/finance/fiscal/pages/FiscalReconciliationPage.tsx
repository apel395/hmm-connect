import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { apiErrorMessage } from "@/utils/apiError";
import { fiscalApi } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const money = (value: unknown) => `Rp ${Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";

const classificationVariant: Record<string, BadgeVariant> = {
  NORMAL: "success",
  FINAL: "default",
  NON_DEDUCTIBLE: "danger",
  KOREKSI_POSITIF: "danger",
  KOREKSI_NEGATIF: "primary",
};

export default function FiscalReconciliationPage() {
  const year = new Date().getFullYear();
  const [dateFrom, setDateFrom] = useState(`${year}-01-01`);
  const [dateTo, setDateTo] = useState(`${year}-12-31`);
  const [open, setOpen] = useState<number | null>(null);

  const query = useQuery({
    queryKey: ["fiscal-reconciliation", { dateFrom, dateTo }],
    queryFn: async () => (await fiscalApi.reconciliation({ date_from: dateFrom, date_to: dateTo })).data,
  });
  const summary = query.data?.summary;
  const lines = query.data?.lines ?? [];
  const unmapped = query.data?.unmapped ?? [];

  const klassBadge = (classification: string) => (
    <Badge variant={classificationVariant[classification] ?? "default"}>{classification.replaceAll("_", " ")}</Badge>
  );

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-6">
        <FiscalWorkspaceHeader />
        <PageHeader
          title="Fiscal Reconciliation"
          description="Commercial profit &amp; loss adjusted by fiscal corrections to derive taxable income (PKP) and estimated corporate income tax (Pasal 31E, 11%)."
          actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>}
        />

        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm font-medium">From
              <Input type="date" className={input} value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
            </label>
            <label className="text-sm font-medium">To
              <Input type="date" className={input} value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
            </label>
            <Button onClick={() => query.refetch()} loading={query.isFetching}>Refresh</Button>
          </div>
        </Card>

        {query.isLoading ? (
          <div className="py-16"><Loading message="Loading fiscal reconciliation…" /></div>
        ) : query.isError ? (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <div className="font-semibold">Fiscal reconciliation could not be loaded.</div>
            <p className="mt-1 text-xs">{apiErrorMessage(query.error, "The reconciliation service did not return a usable response.")}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => query.refetch()}>Try again</Button>
          </div>
        ) : (
          <>
            <ModuleSummary metrics={[
              { label: "Net Commercial Profit", value: money(summary?.laba_bersih_komersial) },
              { label: "Positive Corrections (+)", value: money(summary?.koreksi_positif) },
              { label: "Negative Corrections (−)", value: money(summary?.koreksi_negatif) },
              { label: "Fiscal Profit (PKP)", value: money(summary?.laba_fiskal_pkp) },
              { label: "Corporate Tax Payable (31E)", value: money(summary?.pph_terutang) },
            ]} />

            {unmapped.length > 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <div className="flex items-center gap-2 font-medium"><AlertTriangle className="h-4 w-4" /> {unmapped.length} commercial P&amp;L account(s) have no fiscal mapping</div>
                <ul className="mt-2 list-disc pl-5">
                  {unmapped.map((account) => (
                    <li key={account.commercial_code}>{account.commercial_code} — {account.commercial_name} ({money(account.saldo_komersial)})</li>
                  ))}
                </ul>
              </div>
            )}

            <Card className="p-0">
              <Table variant="grid">
                <THead>
                  <TR>
                    <TH>Fiscal Account</TH><TH>Classification</TH>
                    <TH className="text-right">Commercial Balance</TH>
                    <TH className="text-right">Positive Corr.</TH>
                    <TH className="text-right">Negative Corr.</TH>
                    <TH className="text-right">Fiscal Balance</TH><TH />
                  </TR>
                </THead>
                <TBody>
                  {!lines.length && (
                    <TR><TD colSpan={7} className="py-10 text-center text-slate-500">No P&amp;L activity in the selected period.</TD></TR>
                  )}
                  {lines.map((line) => {
                    const isOpen = open === line.fiscal_account_id;
                    return (
                      <Fragment key={line.fiscal_account_id}>
                        <TR className="cursor-pointer" onClick={() => setOpen(isOpen ? null : line.fiscal_account_id)}>
                          <TD><span className="font-mono font-medium">{line.fiscal_code}</span> <span className="ml-1">{line.fiscal_name}</span></TD>
                          <TD>{klassBadge(line.klasifikasi_fiskal)}</TD>
                          <TD className="text-right tabular-nums">{money(line.saldo_komersial)}</TD>
                          <TD className="text-right tabular-nums">{money(line.koreksi_positif)}</TD>
                          <TD className="text-right tabular-nums">{money(line.koreksi_negatif)}</TD>
                          <TD className="text-right font-semibold tabular-nums">{money(line.saldo_fiskal)}</TD>
                          <TD><ChevronDown className={`h-4 w-4 transition ${isOpen ? "rotate-180" : ""}`} /></TD>
                        </TR>
                        {isOpen && (
                          <TR>
                            <TD colSpan={7} className="bg-slate-50/70 p-0">
                              <Table variant="standard">
                                <THead>
                                  <TR>
                                    <TH className="pl-10">Commercial Account</TH>
                                    <TH className="text-right">Commercial Balance</TH>
                                    <TH className="text-right">Positive Corr.</TH>
                                    <TH className="text-right">Negative Corr.</TH>
                                    <TH className="text-right">Fiscal Balance</TH>
                                  </TR>
                                </THead>
                                <TBody>
                                  {line.accounts.map((account) => (
                                    <TR key={account.commercial_account_id}>
                                      <TD className="pl-10"><span className="font-mono">{account.commercial_code}</span> <span className="ml-1">{account.commercial_name}</span></TD>
                                      <TD className="text-right tabular-nums">{money(account.saldo_komersial)}</TD>
                                      <TD className="text-right tabular-nums">{money(account.koreksi_positif)}</TD>
                                      <TD className="text-right tabular-nums">{money(account.koreksi_negatif)}</TD>
                                      <TD className="text-right tabular-nums">{money(account.saldo_fiskal)}</TD>
                                    </TR>
                                  ))}
                                </TBody>
                              </Table>
                            </TD>
                          </TR>
                        )}
                      </Fragment>
                    );
                  })}
                </TBody>
              </Table>
            </Card>
          </>
        )}
      </div>
    </DataWorkspace>
  );
}

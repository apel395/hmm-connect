import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Printer, RefreshCw } from "lucide-react";
import { ExportButton } from "@/components/common/ReportActions";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import { FORM_UI } from "@/config/formUi";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import SearchableSelect from "@/components/form/SearchableSelect";
import { listDepartments, listLocations, type Department, type Location } from "@/modules/admin/organization/api";
import { apiErrorMessage } from "@/utils/apiError";
import { exportCsv } from "@/utils/exportCsv";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { fiscalApi } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const money = (value: unknown) => `Rp ${Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const num = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const numeric = "whitespace-nowrap text-right tabular-nums";
const input = `${FORM_UI.controlBase} ${FORM_UI.density.compact.control}`;

const classificationVariant: Record<string, BadgeVariant> = {
  NORMAL: "success",
  FINAL: "default",
  NON_DEDUCTIBLE: "danger",
  KOREKSI_POSITIF: "danger",
  KOREKSI_NEGATIF: "primary",
};

type LampiranFilters = {
  fiscal_year: number;
  department_id: number | string;
  location_id: number | string;
};

export default function Lampiran1DPage() {
  const currentYear = new Date().getFullYear();
  const [draft, setDraft] = useState<LampiranFilters>({ fiscal_year: currentYear, department_id: "", location_id: "" });
  const [filters, setFilters] = useState<LampiranFilters>(draft);

  const year = Number(filters.fiscal_year) || currentYear;
  const dateFrom = `${year}-01-01`;
  const dateTo = `${year}-12-31`;

  const departmentFilter = { department_id: filters.department_id ? Number(filters.department_id) : undefined };
  const locationFilter = { location_id: filters.location_id ? Number(filters.location_id) : undefined };

  const departments = useQuery({ queryKey: ["fiscal-l1d-departments"], queryFn: () => listDepartments({ is_active: true }) });
  const locations = useQuery({ queryKey: ["fiscal-l1d-locations"], queryFn: () => listLocations({ is_active: true }) });

  const recon = useQuery({
    queryKey: ["fiscal-lampiran-1d-recon", { dateFrom, dateTo, ...departmentFilter, ...locationFilter }],
    queryFn: async () => (await fiscalApi.reconciliation({ date_from: dateFrom, date_to: dateTo, ...departmentFilter, ...locationFilter })).data,
  });
  const balanceSheet = useQuery({
    queryKey: ["fiscal-lampiran-1d-bs", { fiscal_year: year, ...departmentFilter, ...locationFilter }],
    queryFn: async () => (await fiscalApi.fiscalBalanceSheet({ fiscal_year: year, ...departmentFilter, ...locationFilter })).data,
  });

  const lines = recon.data?.lines ?? [];
  const summary = recon.data?.summary;
  const balanceSummary = balanceSheet.data?.summary;
  const sections = balanceSheet.data?.sections ?? [];

  const exportData = () => {
    const headers = ["SPT Account Code", "Name", "Classification", "Commercial", "Non-Taxable Object", "Subject to Final PPh", "Positive Correction", "Negative Correction", "Fiscal"];
    const rows = lines.map((line) => {
      const finalAmount = line.klasifikasi_fiskal === "FINAL" ? line.saldo_komersial : 0;
      return [line.fiscal_code, line.fiscal_name, line.klasifikasi_fiskal ?? "", line.saldo_komersial, 0, finalAmount, line.koreksi_positif, line.koreksi_negatif, line.saldo_fiskal];
    });
    rows.push(["", "TOTAL", "", summary?.laba_bersih_komersial ?? 0, 0, 0, summary?.koreksi_positif ?? 0, summary?.koreksi_negatif ?? 0, summary?.laba_fiskal_pkp ?? 0]);
    exportCsv(`lampiran-1d-jasa-${year}.csv`, headers, rows);
  };

  const isLoading = recon.isLoading || balanceSheet.isLoading;
  const loadError = recon.isError || balanceSheet.isError;

  return (
    <DataWorkspace area="Accounting" className="data-first print-document">
      <div className="space-y-4">
        <div className="hidden print:block">
          <h1 className="text-2xl font-bold">MMH-Connect</h1>
          <h2 className="text-xl font-semibold">Lampiran 1D – Rekonsiliasi Laporan Keuangan (Jasa)</h2>
          <p>Fiscal Year {year} · Coretax PER-11/PJ/2025 Jasa Sector (L1-D)</p>
        </div>
        <div className="print:hidden">
          <FiscalWorkspaceHeader />
        </div>
        <div className="print:hidden">
          <PageHeader
            title="Lampiran 1D (Jasa)"
            description={`Fiscal Year ${year} · Coretax PER-11/PJ/2025 Lampiran L1-D — Rekonsiliasi Laporan Keuangan, Jasa sector. Commercial figures reconciled to fiscal by fiscal classification; balance sheet half below.`}
            actions={
              <>
                <Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>
                <ExportButton scope="filtered" format="csv" onClick={exportData} />
                <Button variant="outline" onClick={() => { recon.refetch(); balanceSheet.refetch(); }}><RefreshCw size={16} /> Refresh</Button>
              </>
            }
          />
        </div>

        <Card className="p-4 print:hidden">
          <form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft }); }}>
            <label>Fiscal Year
              <input required type="number" min={2000} max={2100} className={input} value={draft.fiscal_year} onChange={(event) => setDraft({ ...draft, fiscal_year: Number(event.target.value) })} />
            </label>
            <SearchableSelect
              label="Department"
              value={draft.department_id || undefined}
              disabled={departments.isLoading}
              placeholder={departments.isLoading ? "Loading departments..." : "Type department code or name..."}
              options={(departments.data ?? []).map((department: Department) => ({ id: department.id, label: `${department.code} - ${department.name}`, keywords: [String(department.code), String(department.name)] }))}
              onChange={(id) => setDraft({ ...draft, department_id: id ?? "" })}
            />
            <SearchableSelect
              label="Location"
              value={draft.location_id || undefined}
              disabled={locations.isLoading}
              placeholder={locations.isLoading ? "Loading locations..." : "Type location code or name..."}
              options={(locations.data ?? []).map((location: Location) => ({ id: location.id, label: `${location.code} - ${location.name}`, keywords: [String(location.code), String(location.name)] }))}
              onChange={(id) => setDraft({ ...draft, location_id: id ?? "" })}
            />
            <div className="flex items-end gap-2">
              <Button type="submit">Apply</Button>
              <Button type="button" variant="outline" onClick={() => {
                const reset: LampiranFilters = { fiscal_year: currentYear, department_id: "", location_id: "" };
                setDraft(reset);
                setFilters(reset);
              }}>Reset</Button>
            </div>
          </form>
        </Card>

        {isLoading ? (
          <div className="py-16"><Loading message="Loading Lampiran 1D…" /></div>
        ) : loadError ? (
          <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            <div className="font-semibold">Lampiran 1D could not be loaded.</div>
            <p className="mt-1 text-xs">{apiErrorMessage(recon.error ?? balanceSheet.error, "The fiscal report service did not return a usable response.")}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => { recon.refetch(); balanceSheet.refetch(); }}>Try again</Button>
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

            <Card className="p-0">
              <div className="border-b px-4 py-3">
                <h2 className="font-semibold">Income Statement (L1-D Reconciliation)</h2>
                <p className="text-xs text-slate-500">Each commercial line is reconciled to fiscal; the "Non-Taxable Object" column is blank because it is not yet modeled separately.</p>
              </div>
              <div className="overflow-x-auto">
                <Table variant="grid">
                  <THead>
                    <TR>
                      <TH>SPT Account Code</TH><TH>Name</TH><TH>Classification</TH>
                      <TH className={numeric}>Commercial</TH>
                      <TH className={numeric}>Non-Taxable</TH>
                      <TH className={numeric}>Final PPh</TH>
                      <TH className={numeric}>Positive Corr.</TH>
                      <TH className={numeric}>Negative Corr.</TH>
                      <TH className={numeric}>Fiscal</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {!lines.length && (
                      <TR><TD colSpan={9} className="py-10 text-center text-slate-500">No P&amp;L activity in the fiscal year.</TD></TR>
                    )}
                    {lines.map((line) => {
                      const finalAmount = line.klasifikasi_fiskal === "FINAL" ? line.saldo_komersial : 0;
                      return (
                        <TR key={line.fiscal_account_id}>
                          <TD className="font-mono font-medium">{line.fiscal_code}</TD>
                          <TD>{line.fiscal_name}</TD>
                          <TD><Badge variant={classificationVariant[line.klasifikasi_fiskal] ?? "default"}>{line.klasifikasi_fiskal.replaceAll("_", " ")}</Badge></TD>
                          <TD className={numeric}>{num(line.saldo_komersial)}</TD>
                          <TD className={numeric}>0</TD>
                          <TD className={numeric}>{num(finalAmount)}</TD>
                          <TD className={numeric}>{num(line.koreksi_positif)}</TD>
                          <TD className={numeric}>{num(line.koreksi_negatif)}</TD>
                          <TD className={`${numeric} font-semibold`}>{num(line.saldo_fiskal)}</TD>
                        </TR>
                      );
                    })}
                    <TR className="bg-slate-100 font-semibold">
                      <TD colSpan={3}>TOTAL</TD>
                      <TD className={numeric}>{num(summary?.laba_bersih_komersial)}</TD>
                      <TD className={numeric}>0</TD>
                      <TD className={numeric}>0</TD>
                      <TD className={numeric}>{num(summary?.koreksi_positif)}</TD>
                      <TD className={numeric}>{num(summary?.koreksi_negatif)}</TD>
                      <TD className={`${numeric} font-bold`}>{num(summary?.laba_fiskal_pkp)}</TD>
                    </TR>
                  </TBody>
                </Table>
              </div>
            </Card>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Table variant="grid" stickyHeader className="min-w-full">
                  <THead><TR><TH>Statement of Financial Position (Balance Sheet) — Assets</TH><TH className={numeric}>Fiscal</TH></TR></THead>
                  <TBody>
                    {sections.filter((section) => section.code === "ASET").flatMap((section) => section.sections.map((sub) => (
                      <Fragment key={sub.code}>
                        <TR className="bg-slate-50 font-semibold"><TD className="pl-6">{sub.label}</TD><TD className={numeric}>{money(sub.total)}</TD></TR>
                        {sub.lines.map((line) => (
                          <TR key={`${sub.code}-${line.fiscal_code}`}><TD className="pl-10">{line.fiscal_code} — {line.account_name}</TD><TD className={numeric}>{money(line.amount)}</TD></TR>
                        ))}
                      </Fragment>
                    )))}
                    {!sections.length && (
                      <TR><TD colSpan={2} className="py-10 text-center text-slate-500">No fiscal balance sheet sections.</TD></TR>
                    )}
                    <TR className="bg-slate-100 font-bold"><TD>Total Assets</TD><TD className={numeric}>{money(balanceSummary?.total_assets)}</TD></TR>
                  </TBody>
                </Table>
              </div>
              <div>
                <Table variant="grid" stickyHeader className="min-w-full">
                  <THead><TR><TH>Statement of Financial Position (Balance Sheet) — Liabilities &amp; Equity</TH><TH className={numeric}>Fiscal</TH></TR></THead>
                  <TBody>
                    {sections.filter((section) => section.code === "KEWAJIBAN_EKUITAS").flatMap((section) => section.sections.map((sub) => (
                      <Fragment key={sub.code}>
                        <TR className="bg-slate-50 font-semibold"><TD className="pl-6">{sub.label}</TD><TD className={numeric}>{money(sub.total)}</TD></TR>
                        {sub.lines.map((line) => (
                          <TR key={`${sub.code}-${line.fiscal_code}`}><TD className="pl-10">{line.fiscal_code} — {line.account_name}</TD><TD className={numeric}>{money(line.amount)}</TD></TR>
                        ))}
                      </Fragment>
                    )))}
                    {!sections.length && (
                      <TR><TD colSpan={2} className="py-10 text-center text-slate-500">No fiscal balance sheet sections.</TD></TR>
                    )}
                    <TR className="bg-slate-100 font-bold"><TD>Total Liabilities &amp; Equity</TD><TD className={numeric}>{money(balanceSummary?.total_liabilities_and_equity)}</TD></TR>
                  </TBody>
                </Table>
              </div>
            </div>
          </>
        )}
      </div>
    </DataWorkspace>
  );
}

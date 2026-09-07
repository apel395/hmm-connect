import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Printer, RefreshCw } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import SearchableSelect from "@/components/form/SearchableSelect";
import { listDepartments, listLocations } from "@/modules/admin/organization/api";
import { exportCsv } from "@/utils/exportCsv";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { fiscalApi } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const numeric = "whitespace-nowrap text-right tabular-nums";

const clsVariant: Record<string, string> = {
  NORMAL: "bg-emerald-50 text-emerald-700",
  FINAL: "bg-slate-100 text-slate-600",
  NON_DEDUCTIBLE: "bg-red-50 text-red-700",
  KOREKSI_POSITIF: "bg-red-50 text-red-700",
  KOREKSI_NEGATIF: "bg-blue-50 text-blue-700",
};

interface ReconLine {
  fiscal_account_id: number;
  fiscal_code: string;
  fiscal_name: string;
  klasifikasi_fiskal: string;
  saldo_komersial: number;
  koreksi_positif: number;
  koreksi_negatif: number;
  saldo_fiskal: number;
}

export default function Lampiran1DPage() {
  const currentYear = new Date().getFullYear();
  const [draft, setDraft] = useState<any>({ fiscal_year: currentYear, department_id: "", location_id: "" });
  const [filters, setFilters] = useState<any>(draft);

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
  const ds = useQuery({
    queryKey: ["fiscal-lampiran-1d-bs", { fiscal_year: year, ...departmentFilter, ...locationFilter }],
    queryFn: async () => (await fiscalApi.fiscalBalanceSheet({ fiscal_year: year, ...departmentFilter, ...locationFilter })).data,
  });

  const reconData: any = recon.data;
  const lines: ReconLine[] = reconData?.lines ?? [];
  const summary = reconData?.summary ?? {};
  const s = ds.data?.summary;
  const sections: any[] = ds.data?.sections ?? [];

  const exportData = () => {
    const headers = ["Kode Akun", "Uraian", "Klasifikasi", "Komersial", "Bukan Objek Pajak", "Dikenakan PPh Final", "Koreksi Positif", "Koreksi Negatif", "Fiskal"];
    const rows = lines.map((l) => {
      const finalAmount = l.klasifikasi_fiskal === "FINAL" ? l.saldo_komersial : 0;
      return [l.fiscal_code, l.fiscal_name, l.klasifikasi_fiskal ?? "", l.saldo_komersial, 0, finalAmount, l.koreksi_positif, l.koreksi_negatif, l.saldo_fiskal];
    });
    rows.push(["", "TOTAL", "", summary.laba_bersih_komersial ?? 0, 0, 0, summary.koreksi_positif ?? 0, summary.koreksi_negatif ?? 0, summary.laba_fiskal_pkp ?? 0]);
    exportCsv(`lampiran-1d-jasa-${year}.csv`, headers, rows);
  };

  const isLoading = recon.isLoading || ds.isLoading;

  return (
    <div className="print-document space-y-4">
      <div className="hidden print:block">
        <h1 className="text-2xl font-bold">HMM-Connect</h1>
        <h2 className="text-xl font-semibold">Lampiran 1D – Rekonsiliasi Laporan Keuangan (Jasa)</h2>
        <p>Fiscal Year {year} · Coretax PER-11/PJ/2025 Sektor Jasa (L1-D)</p>
      </div>
      <div className="print:hidden">
        <FiscalWorkspaceHeader />
      </div>
      <div className="print:hidden">
        <PageHeader title="Lampiran 1D (Jasa)" description={`Fiscal Year ${year} · Coretax PER-11/PJ/2025 Lampiran L1-D — Rekonsiliasi Laporan Keuangan sektor Jasa. Komersial figures reconciled to fiskal by fiscal classification; balance sheet (neraca) half below.`} actions={
          <>
            <Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>
            <Button variant="outline" onClick={exportData}><Download size={16} /> CSV</Button>
            <Button variant="outline" onClick={() => { recon.refetch(); ds.refetch(); }}><RefreshCw size={16} /> Refresh</Button>
          </>
        } />
      </div>
      <Card className="p-4 print:hidden">
        <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => { e.preventDefault(); setFilters({ ...draft }); }}>
          <label>Fiscal Year
            <input required type="number" min={2000} max={2100} className="h-9 w-full rounded border px-3 text-[13px]" value={draft.fiscal_year} onChange={(e) => setDraft({ ...draft, fiscal_year: Number(e.target.value) })} />
          </label>
          <SearchableSelect label="Department" value={draft.department_id || undefined} disabled={departments.isLoading} placeholder={departments.isLoading ? "Loading departments..." : "Type department code or name..."} options={(departments.data ?? []).map((d: any) => ({ id: d.id, label: `${d.code} - ${d.name}`, keywords: [String(d.code), String(d.name)] }))} onChange={(id) => setDraft({ ...draft, department_id: id ?? "" })} />
          <SearchableSelect label="Location" value={draft.location_id || undefined} disabled={locations.isLoading} placeholder={locations.isLoading ? "Loading locations..." : "Type location code or name..."} options={(locations.data ?? []).map((l: any) => ({ id: l.id, label: `${l.code} - ${l.name}`, keywords: [String(l.code), String(l.name)] }))} onChange={(id) => setDraft({ ...draft, location_id: id ?? "" })} />
          <div className="flex items-end gap-2">
            <Button type="submit">Apply</Button>
            <Button type="button" variant="outline" onClick={() => { setDraft({ fiscal_year: currentYear, department_id: "", location_id: "" }); setFilters({ fiscal_year: currentYear, department_id: "", location_id: "" }); }}>Reset</Button>
          </div>
        </form>
      </Card>

      {isLoading ? <div className="py-16"><Loading /></div> : recon.isError || ds.isError ? (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-red-700">Lampiran 1D could not be loaded.</div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Laba Bersih Komersial</div><div className="mt-2 text-xl font-bold">{money(summary.laba_bersih_komersial)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Koreksi Positif (+)</div><div className="mt-2 text-xl font-bold text-red-700">{money(summary.koreksi_positif)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Koreksi Negatif (−)</div><div className="mt-2 text-xl font-bold text-blue-700">{money(summary.koreksi_negatif)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Laba Fiskal (PKP)</div><div className="mt-2 text-xl font-bold">{money(summary.laba_fiskal_pkp)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">PPh Terutang (31E)</div><div className="mt-2 text-xl font-bold text-emerald-700">{money(summary.pph_terutang)}</div></Card>
          </div>

          <Card className="p-0">
            <div className="border-b px-4 py-3">
              <h2 className="font-semibold">Laporan Laba Rugi (Rekonsiliasi L1-D)</h2>
              <p className="text-xs text-slate-500">Setiap baris komersial direkonsiliasi ke fiskal; kolom“Bukan Objek Pajak” dikosongkan karena belum dimodelkan secara terpisah.</p>
            </div>
            <div className="overflow-x-auto">
              <Table variant="grid">
                <THead><TR>
                  <TH>Kode Akun SPT</TH><TH>Uraian</TH><TH>Klasifikasi</TH>
                  <TH className={numeric}>Komersial</TH>
                  <TH className={numeric}>Bukan Objek</TH>
                  <TH className={numeric}>PPh Final</TH>
                  <TH className={numeric}>Koreksi +</TH>
                  <TH className={numeric}>Koreksi −</TH>
                  <TH className={numeric}>Fiskal</TH>
                </TR></THead>
                <TBody>
                  {lines.length === 0 && <TR><TD colSpan={9} className="py-10 text-center text-slate-500">No P&amp;L activity in the fiscal year.</TD></TR>}
                  {lines.map((l) => {
                    const finalAmount = l.klasifikasi_fiskal === "FINAL" ? l.saldo_komersial : 0;
                    return (
                      <TR key={l.fiscal_account_id}>
                        <TD className="font-mono font-medium">{l.fiscal_code}</TD>
                        <TD>{l.fiscal_name}</TD>
                        <TD><span className={`rounded px-2 py-1 text-xs font-medium ${clsVariant[l.klasifikasi_fiskal] ?? "bg-slate-100 text-slate-600"}`}>{l.klasifikasi_fiskal.replaceAll("_", " ")}</span></TD>
                        <TD className={numeric}>{num(l.saldo_komersial)}</TD>
                        <TD className={numeric}>0</TD>
                        <TD className={numeric}>{num(finalAmount)}</TD>
                        <TD className={numeric}>{num(l.koreksi_positif)}</TD>
                        <TD className={numeric}>{num(l.koreksi_negatif)}</TD>
                        <TD className={`${numeric} font-semibold`}>{num(l.saldo_fiskal)}</TD>
                      </TR>
                    );
                  })}
                  <TR className="bg-slate-100 font-semibold">
                    <TD colSpan={3}>TOTAL</TD>
                    <TD className={numeric}>{num(summary.laba_bersih_komersial)}</TD>
                    <TD className={numeric}>0</TD>
                    <TD className={numeric}>0</TD>
                    <TD className={numeric}>{num(summary.koreksi_positif)}</TD>
                    <TD className={numeric}>{num(summary.koreksi_negatif)}</TD>
                    <TD className={`${numeric} font-bold`}>{num(summary.laba_fiskal_pkp)}</TD>
                  </TR>
                </TBody>
              </Table>
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Table variant="grid" stickyHeader className="min-w-full">
                <THead><TR><TH>Laporan Posisi Keuangan (Neraca) — Aktiva</TH><TH className={numeric}>Fiskal</TH></TR></THead>
                <TBody>
                  {sections.filter((sec: any) => sec.code === "ASET").flatMap((sec: any) => sec.sections.map((sub: any) => (
                    <Fragment key={sub.code}>
                      <TR className="bg-slate-50 font-semibold"><TD className="pl-6">{sub.label}</TD><TD className={numeric}>{money(sub.total)}</TD></TR>
                      {sub.lines.map((line: any) => (
                        <TR key={`${sub.code}-${line.fiscal_code}`}><TD className="pl-10">{line.fiscal_code} — {line.account_name}</TD><TD className={numeric}>{money(line.amount)}</TD></TR>
                      ))}
                    </Fragment>
                  )))}
                  <TR className="bg-slate-100 font-bold"><TD>Total Aktiva</TD><TD className={numeric}>{money(s?.total_assets)}</TD></TR>
                </TBody>
              </Table>
            </div>
            <div>
              <Table variant="grid" stickyHeader className="min-w-full">
                <THead><TR><TH>Laporan Posisi Keuangan (Neraca) — Kewajiban &amp; Ekuitas</TH><TH className={numeric}>Fiskal</TH></TR></THead>
                <TBody>
                  {sections.filter((sec: any) => sec.code === "KEWAJIBAN_EKUITAS").flatMap((sec: any) => sec.sections.map((sub: any) => (
                    <Fragment key={sub.code}>
                      <TR className="bg-slate-50 font-semibold"><TD className="pl-6">{sub.label}</TD><TD className={numeric}>{money(sub.total)}</TD></TR>
                      {sub.lines.map((line: any) => (
                        <TR key={`${sub.code}-${line.fiscal_code}`}><TD className="pl-10">{line.fiscal_code} — {line.account_name}</TD><TD className={numeric}>{money(line.amount)}</TD></TR>
                      ))}
                    </Fragment>
                  )))}
                  <TR className="bg-slate-100 font-bold"><TD>Total Kewajiban &amp; Ekuitas</TD><TD className={numeric}>{money(s?.total_liabilities_and_equity)}</TD></TR>
                </TBody>
              </Table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
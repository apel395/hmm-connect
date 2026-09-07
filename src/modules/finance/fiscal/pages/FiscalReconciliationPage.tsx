import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {AlertTriangle, ChevronDown, Printer} from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { fiscalApi } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";

interface Line {
  fiscal_account_id: number;
  fiscal_code: string;
  fiscal_name: string;
  klasifikasi_fiskal: string;
  saldo_komersial: number;
  koreksi_positif: number;
  koreksi_negatif: number;
  saldo_fiskal: number;
  accounts: Array<Record<string, unknown>>;
}

const clsVariant: Record<string, string> = {
  NORMAL: "bg-emerald-50 text-emerald-700",
  FINAL: "bg-slate-100 text-slate-600",
  NON_DEDUCTIBLE: "bg-red-50 text-red-700",
  KOREKSI_POSITIF: "bg-red-50 text-red-700",
  KOREKSI_NEGATIF: "bg-blue-50 text-blue-700",
};

export default function FiscalReconciliationPage() {
  const year = new Date().getFullYear();
  const [dateFrom, setDateFrom] = useState(`${year}-01-01`);
  const [dateTo, setDateTo] = useState(`${year}-12-31`);
  const [open, setOpen] = useState<number | null>(null);

  const q = useQuery({
    queryKey: ["fiscal-reconciliation", { dateFrom, dateTo }],
    queryFn: async () => (await fiscalApi.reconciliation({ date_from: dateFrom, date_to: dateTo })).data,
  });
  const data: any = q.data;
  const summary = data?.summary ?? {};
  const lines: Line[] = data?.lines ?? [];
  const unmapped: any[] = data?.unmapped ?? [];

  const klassBadge = (k: string) => (
    <span className={`rounded px-2 py-1 text-xs font-medium ${clsVariant[k] ?? "bg-slate-100 text-slate-600"}`}>{k.replaceAll("_", " ")}</span>
  );

  return (
    <div className="space-y-6">
      <FiscalWorkspaceHeader />
      <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Fiscal Reconciliation" description="Commercial profit &amp; loss adjusted by fiscal corrections to derive taxable income (PKP) and estimated corporate income tax (Pasal 31E, 11%)." />

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm font-medium">From
            <Input type="date" className={input} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </label>
          <label className="text-sm font-medium">To
            <Input type="date" className={input} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </label>
          <Button onClick={() => q.refetch()} loading={q.isFetching}>Refresh</Button>
        </div>
      </Card>

      {q.isLoading ? <div className="py-16"><Loading /></div> : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Net Commercial Profit</div><div className="mt-2 text-xl font-bold">{money(summary.laba_bersih_komersial)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Positive Corrections (+)</div><div className="mt-2 text-xl font-bold text-red-700">{money(summary.koreksi_positif)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Negative Corrections (−)</div><div className="mt-2 text-xl font-bold text-blue-700">{money(summary.koreksi_negatif)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Fiscal Profit (PKP)</div><div className="mt-2 text-xl font-bold">{money(summary.laba_fiskal_pkp)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Corporate Tax Payable (31E)</div><div className="mt-2 text-xl font-bold text-emerald-700">{money(summary.pph_terutang)}</div></Card>
          </div>

          {unmapped.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <div className="flex items-center gap-2 font-medium"><AlertTriangle className="h-4 w-4" /> {unmapped.length} commercial P&amp;L account(s) have no fiscal mapping</div>
              <ul className="mt-2 list-disc pl-5">{unmapped.map((u) => <li key={u.commercial_code}>{u.commercial_code} — {u.commercial_name} ({money(u.saldo_komersial)})</li>)}</ul>
            </div>
          )}

          <Card className="p-0">
            <Table variant="grid"><THead><TR><TH>Fiscal Account</TH><TH>Classification</TH><TH className="text-right">Commercial Balance</TH><TH className="text-right">Positive Corr.</TH><TH className="text-right">Negative Corr.</TH><TH className="text-right">Fiscal Balance</TH><TH /></TR></THead>
            <TBody>
              {lines.length === 0 && <TR><TD colSpan={7} className="py-10 text-center text-slate-500">No P&amp;L activity in the selected period.</TD></TR>}
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
                      <TD className="text-right tabular-nums font-semibold">{money(line.saldo_fiskal)}</TD>
                      <TD><ChevronDown className={`h-4 w-4 transition ${isOpen ? "rotate-180" : ""}`} /></TD>
                    </TR>
                    {isOpen && (
                      <TR>
                        <TD colSpan={7} className="bg-slate-50/70 p-0">
                          <Table variant="standard"><THead><TR><TH className="pl-10">Commercial Account</TH><TH className="text-right">Commercial Balance</TH><TH className="text-right">Positive Corr.</TH><TH className="text-right">Negative Corr.</TH><TH className="text-right">Fiscal Balance</TH></TR></THead>
                          <TBody>{line.accounts.map((a: any) => (
                            <TR key={a.commercial_account_id}><TD className="pl-10"><span className="font-mono">{a.commercial_code}</span> <span className="ml-1">{a.commercial_name}</span></TD><TD className="text-right tabular-nums">{money(a.saldo_komersial)}</TD><TD className="text-right tabular-nums">{money(a.koreksi_positif)}</TD><TD className="text-right tabular-nums">{money(a.koreksi_negatif)}</TD><TD className="text-right tabular-nums">{money(a.saldo_fiskal)}</TD></TR>
                          ))}</TBody></Table>
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
  );
}
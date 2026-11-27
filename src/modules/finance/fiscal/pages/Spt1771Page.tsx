import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, FileText, Landmark, RefreshCw, Save, Trash2, Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { apiErrorMessage } from "@/utils/apiError";
import { fiscalApi, type TaxCredit, type TaxCreditCreate } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const money = (value: unknown) => `Rp ${Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";
const CREDIT_TYPES: TaxCreditCreate["credit_type"][] = ["PPh 22", "PPh 23", "PPh 24", "PPh 25", "OTHER"];

export default function Spt1771Page() {
  const year = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(year);
  const [kompensasi, setKompensasi] = useState("");
  const queryClient = useQueryClient();

  const [profileForm, setProfileForm] = useState<Record<string, string>>({});
  const [creditForm, setCreditForm] = useState<{ credit_type: TaxCreditCreate["credit_type"]; amount: string; description: string; payment_date: string }>({
    credit_type: "PPh 25", amount: "", description: "", payment_date: "",
  });

  const report = useQuery({
    queryKey: ["spt-1771", { taxYear, kompensasi }],
    queryFn: async () => (await fiscalApi.sptReport({ tax_year: taxYear, kompensasi_kerugian: kompensasi ? Number(kompensasi) : undefined })).data,
  });
  const profileQuery = useQuery({
    queryKey: ["spt-1771-profile", taxYear],
    queryFn: async () => (await fiscalApi.sptProfile(taxYear)).data,
  });
  const creditsQuery = useQuery({
    queryKey: ["spt-1771-credits", taxYear],
    queryFn: async () => (await fiscalApi.sptCredits(taxYear)).data,
  });

  const profileReady = !!profileQuery.data;
  const profileMerge = useMemo(() => {
    const base = (profileQuery.data ?? {}) as Record<string, string | null | undefined>;
    const keys = ["npwp", "company_name", "address", "city", "klu", "phone", "email", "representative_name"];
    const merged: Record<string, string> = {};
    for (const key of keys) merged[key] = profileForm[key] ?? base[key] ?? "";
    return merged;
  }, [profileQuery.data, profileForm]);

  const saveProfile = useMutation({
    mutationFn: () => fiscalApi.sptUpsertProfile(taxYear, profileMerge),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["spt-1771-profile"] });
      queryClient.invalidateQueries({ queryKey: ["spt-1771"] });
      toast.success("Tax profile saved");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Could not save tax profile")),
  });

  const addCredit = useMutation({
    mutationFn: () => fiscalApi.sptCreateCredit({
      tax_year: taxYear,
      credit_type: creditForm.credit_type,
      amount: Number(creditForm.amount),
      description: creditForm.description || null,
      payment_date: creditForm.payment_date || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["spt-1771-credits"] });
      queryClient.invalidateQueries({ queryKey: ["spt-1771"] });
      setCreditForm({ credit_type: "PPh 25", amount: "", description: "", payment_date: "" });
      toast.success("Tax credit added");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Could not add tax credit")),
  });

  const deleteCredit = useMutation({
    mutationFn: (id: number) => fiscalApi.sptDeleteCredit(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["spt-1771-credits"] });
      queryClient.invalidateQueries({ queryKey: ["spt-1771"] });
      toast.success("Tax credit removed");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Could not remove tax credit")),
  });

  const formField = (key: string, label: string, cols?: string) => (
    <label className={cols}>
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <Input className={input} value={profileMerge[key]} onChange={(event) => setProfileForm((previous) => ({ ...previous, [key]: event.target.value }))} />
    </label>
  );

  const Row = ({ label, value, strong }: { label: string; value: unknown; strong?: boolean }) => (
    <TR><TD className="text-slate-600">{label}</TD><TD className={`text-right tabular-nums ${strong ? "font-bold" : ""}`}>{money(value)}</TD></TR>
  );

  const sectionA = report.data?.section_i_a ?? {};
  const sectionII = report.data?.section_ii ?? {};
  const sectionIII = report.data?.section_iii ?? {};
  const credits = creditsQuery.data ?? [];
  const isLoading = report.isLoading;

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-6">
        <FiscalWorkspaceHeader />
        <PageHeader
          title="SPT Tahunan 1771"
          description="Annual corporate income tax return — commercial P&L, fiscal reconciliation, and corporate tax computation (Pasal 31E)."
          actions={
            <>
              <Input type="number" className={`${input} w-28`} value={taxYear} onChange={(event) => setTaxYear(Number(event.target.value))} />
              <Button variant="outline" onClick={() => report.refetch()} loading={report.isFetching}><RefreshCw className="mr-1 h-4 w-4" />Refresh</Button>
              <Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>
            </>
          }
        />

        {isLoading ? (
          <div className="py-16"><Loading message="Loading SPT 1771…" /></div>
        ) : (
          <>
            {report.isError && (
              <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
                <div className="font-semibold">SPT 1771 could not be loaded.</div>
                <p className="mt-1 text-xs">{apiErrorMessage(report.error, "The annual tax report service did not return a usable response.")}</p>
                <Button className="mt-3" size="sm" variant="outline" onClick={() => report.refetch()}>Try again</Button>
              </div>
            )}
            <ModuleSummary metrics={[
              { label: "Gross Revenue", value: money(sectionA.peredaran_usaha) },
              { label: "Fiscal Profit", value: money(sectionII.laba_fiskal) },
              { label: "Taxable Income (PKP)", value: money(sectionII.penghasilan_kena_pajak) },
              { label: "Tax Payable", value: money(sectionIII.pph_terutang) },
              { label: "Tax Credits", value: money(sectionIII.total_kredit_pajak) },
            ]} />

            {profileQuery.isError && (
              <div role="alert" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                Company tax profile could not be loaded. {apiErrorMessage(profileQuery.error, "You can still review the report and retry later.")}
              </div>
            )}

            <Card className="p-4">
              <div className="mb-3 flex items-center gap-2 font-semibold">
                <Building2 className="h-4 w-4" /> Company Tax Profile
                {profileQuery.isLoading && <span className="text-xs font-normal text-slate-500">Loading profile…</span>}
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {formField("npwp", "NPWP")}
                {formField("company_name", "Company Name")}
                {formField("klu", "KLU")}
                {formField("representative_name", "Representative")}
                {formField("phone", "Phone")}
                {formField("email", "Email")}
                {formField("city", "City")}
                {formField("address", "Address", "sm:col-span-2 lg:col-span-4")}
              </div>
              <div className="mt-3">
                <Button size="sm" onClick={() => saveProfile.mutate()} loading={saveProfile.isPending}><Save className="mr-1 h-4 w-4" />Save Profile</Button>
                {!profileReady && <span className="ml-3 text-xs text-amber-600">No profile saved for {taxYear} yet.</span>}
              </div>
            </Card>

            <div className="grid gap-6 lg:grid-cols-3">
              <Card className="p-4 lg:col-span-3">
                <div className="mb-3 flex items-center gap-2 font-semibold"><FileText className="h-4 w-4" /> I-A. Profit &amp; Loss</div>
                <Table variant="grid">
                  <THead><TR><TH>Line Item</TH><TH className="text-right">Amount</TH></TR></THead>
                  <TBody>
                    <Row label="Gross Revenue" value={sectionA.peredaran_usaha} />
                    <Row label="Non-Business Income" value={sectionA.penghasilan_luar_usaha} />
                    <Row label="Total Gross Income" value={sectionA.total_penghasilan_bruto} strong />
                    <Row label="Cost of Goods Sold" value={sectionA.harga_pokok_penjualan} />
                    <Row label="Gross Profit" value={sectionA.laba_kotor_usaha} strong />
                    <Row label="Business Expenses" value={sectionA.biaya_usaha} />
                    <Row label="Operating Profit" value={sectionA.laba_usaha} strong />
                    <Row label="Non-Business Expenses" value={sectionA.biaya_luar_usaha} />
                    <Row label="Profit Before Tax (Commercial)" value={sectionA.laba_sebelum_pajak} strong />
                  </TBody>
                </Table>
              </Card>

              <Card className="p-4">
                <div className="mb-3 flex items-center gap-2 font-semibold"><Landmark className="h-4 w-4" /> II. Fiscal Reconciliation</div>
                <Table variant="grid">
                  <THead><TR><TH>Line Item</TH><TH className="text-right">Amount</TH></TR></THead>
                  <TBody>
                    <Row label="Positive Fiscal Corrections" value={sectionII.koreksi_fiskal_positif} />
                    <Row label="Negative Fiscal Corrections" value={sectionII.koreksi_fiskal_negatif} />
                    <Row label="Fiscal Profit" value={sectionII.laba_fiskal} strong />
                    <TR>
                      <TD className="text-slate-600">Loss Carry-forward</TD>
                      <TD className="text-right">
                        <Input type="number" className={`${input} h-8 w-32`} value={kompensasi} onChange={(event) => setKompensasi(event.target.value)} />
                      </TD>
                    </TR>
                    <Row label="Taxable Income (PKP)" value={sectionII.penghasilan_kena_pajak} strong />
                  </TBody>
                </Table>
              </Card>

              <Card className="p-4">
                <div className="mb-3 flex items-center gap-2 font-semibold"><FileText className="h-4 w-4" /> III. PPh Computation</div>
                <Table variant="grid">
                  <THead><TR><TH>Line Item</TH><TH className="text-right">Amount</TH></TR></THead>
                  <TBody>
                    <TR><TD className="text-slate-600">PPh Rate</TD><TD className="text-right">{Number(sectionIII.pph_rate ?? 0) * 100}%</TD></TR>
                    <Row label="Tax Payable" value={sectionIII.pph_terutang} strong />
                    <Row label="Total Tax Credits" value={sectionIII.total_kredit_pajak} />
                    {sectionIII.is_lebih_bayar ? (
                      <Row label="Overpaid Tax" value={sectionIII.pph_lebih_bayar} strong />
                    ) : (
                      <Row label="Underpaid Tax" value={sectionIII.pph_kurang_bayar} strong />
                    )}
                  </TBody>
                </Table>
                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries((sectionIII.kredit_pajak as Record<string, unknown> | undefined) ?? {}).map(([key, value]) => (
                    <Badge key={key}>{key}: {money(value)}</Badge>
                  ))}
                </div>
              </Card>
            </div>

            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold"><Landmark className="h-4 w-4" /> Tax Credits</div>
              </div>
              {creditsQuery.isError && (
                <div role="alert" className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  Tax credits could not be loaded. {apiErrorMessage(creditsQuery.error, "You can still add a new credit.")}
                </div>
              )}
              <div className="mb-3 grid gap-2 sm:grid-cols-5">
                <select className={input} value={creditForm.credit_type} onChange={(event) => setCreditForm({ ...creditForm, credit_type: event.target.value as TaxCreditCreate["credit_type"] })}>
                  {CREDIT_TYPES.map((type) => <option key={type}>{type}</option>)}
                </select>
                <Input type="number" className={input} placeholder="Amount" value={creditForm.amount} onChange={(event) => setCreditForm({ ...creditForm, amount: event.target.value })} />
                <Input type="date" className={input} value={creditForm.payment_date} onChange={(event) => setCreditForm({ ...creditForm, payment_date: event.target.value })} />
                <Input className={`${input} sm:col-span-2`} placeholder="Description" value={creditForm.description} onChange={(event) => setCreditForm({ ...creditForm, description: event.target.value })} />
              </div>
              <Button size="sm" onClick={() => addCredit.mutate()} loading={addCredit.isPending} disabled={!creditForm.amount}>Add Credit</Button>
              {creditsQuery.isLoading && <div className="mt-3 text-xs text-slate-500">Loading tax credits…</div>}
              <Table variant="grid" className="mt-3">
                <THead><TR><TH>Type</TH><TH>Date</TH><TH>Description</TH><TH className="text-right">Amount</TH><TH /></TR></THead>
                <TBody>
                  {!credits.length && (
                    <TR><TD colSpan={5} className="py-6 text-center text-slate-500">No tax credits recorded.</TD></TR>
                  )}
                  {credits.map((credit: TaxCredit) => (
                    <TR key={credit.id}>
                      <TD><Badge>{credit.credit_type}</Badge></TD>
                      <TD>{credit.payment_date || "—"}</TD>
                      <TD>{credit.description || "—"}</TD>
                      <TD className="text-right tabular-nums">{money(credit.amount)}</TD>
                      <TD><Button size="xs" variant="outline" loading={deleteCredit.isPending && deleteCredit.variables === credit.id} onClick={() => deleteCredit.mutate(credit.id)}><Trash2 className="h-3 w-3" /></Button></TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </Card>
          </>
        )}
      </div>
    </DataWorkspace>
  );
}

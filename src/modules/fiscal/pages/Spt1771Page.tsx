import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, FileText, Landmark, RefreshCw, Save, Trash2 } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { fiscalApi } from "../api";
import FiscalWorkspaceHeader from "../FiscalWorkspaceHeader";

const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";
const CREDIT_TYPES = ["PPh 22", "PPh 23", "PPh 24", "PPh 25", "OTHER"];

export default function Spt1771Page() {
  const year = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(year);
  const [kompensasi, setKompensasi] = useState("");
  const qc = useQueryClient();

  const [profileForm, setProfileForm] = useState<Record<string, string>>({});
  const [creditForm, setCreditForm] = useState({ credit_type: "PPh 25", amount: "", description: "", payment_date: "" });

  const q = useQuery({
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

  const data: any = q.data;
  const ia: any = data?.section_i_a ?? {};
  const ii: any = data?.section_ii ?? {};
  const iii: any = data?.section_iii ?? {};

  const profileReady = !!profileQuery.data;
  const profileMerge = useMemo(() => {
    const base = profileQuery.data ?? {};
    const keys = ["npwp", "company_name", "address", "city", "klu", "phone", "email", "representative_name"];
    const out: Record<string, string> = {};
    for (const k of keys) out[k] = profileForm[k] ?? base[k] ?? "";
    return out;
  }, [profileQuery.data, profileForm]);

  const saveProfile = useMutation({
    mutationFn: () => fiscalApi.sptUpsertProfile(taxYear, profileMerge),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spt-1771-profile"] });
      qc.invalidateQueries({ queryKey: ["spt-1771"] });
      toast.success("Tax profile saved");
    },
    onError: () => toast.error("Could not save tax profile"),
  });

  const addCredit = useMutation({
    mutationFn: () => fiscalApi.sptCreateCredit({
      tax_year: taxYear,
      credit_type: creditForm.credit_type as any,
      amount: Number(creditForm.amount),
      description: creditForm.description || null,
      payment_date: creditForm.payment_date || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spt-1771-credits"] });
      qc.invalidateQueries({ queryKey: ["spt-1771"] });
      setCreditForm({ credit_type: "PPh 25", amount: "", description: "", payment_date: "" });
      toast.success("Tax credit added");
    },
    onError: () => toast.error("Could not add tax credit"),
  });

  const deleteCredit = useMutation({
    mutationFn: (id: number) => fiscalApi.sptDeleteCredit(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spt-1771-credits"] });
      qc.invalidateQueries({ queryKey: ["spt-1771"] });
      toast.success("Tax credit removed");
    },
  });

  const formFields = (key: string, label: string, cols?: string) => (
    <label className={cols ?? ""}><span className="text-xs font-medium text-slate-500">{label}</span>
      <Input className={input} value={profileMerge[key]} onChange={(e) => setProfileForm((p) => ({ ...p, [key]: e.target.value }))} />
    </label>
  );

  const Row = ({ l, v, strong }: { l: string; v: unknown; strong?: boolean }) => (
    <TR><TD className="text-slate-600">{l}</TD><TD className={`text-right tabular-nums ${strong ? "font-bold" : ""}`}>{money(v)}</TD></TR>
  );

  return (
    <div className="space-y-6">
      <FiscalWorkspaceHeader />
      <PageHeader
        title="SPT Tahunan 1771"
        description="Annual corporate income tax return — commercial P&L, fiscal reconciliation, and corporate tax computation (Pasal 31E)."
        actions={
          <>
            <Input type="number" className={input + " w-28"} value={taxYear} onChange={(e) => setTaxYear(Number(e.target.value))} />
            <Button variant="outline" onClick={() => q.refetch()} loading={q.isFetching}><RefreshCw className="mr-1 h-4 w-4" />Refresh</Button>
          </>
        }
      />

      {q.isLoading ? (
        <div className="py-16"><Loading /></div>
      ) : (
        <>
          <Card className="p-4">
            <div className="mb-3 flex items-center gap-2 font-semibold"><Building2 className="h-4 w-4" /> Company Tax Profile</div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {formFields("npwp", "NPWP")}
              {formFields("company_name", "Company Name")}
              {formFields("klu", "KLU")}
              {formFields("representative_name", "Representative")}
              {formFields("phone", "Phone")}
              {formFields("email", "Email")}
              {formFields("city", "City")}
              {formFields("address", "Address", "sm:col-span-2 lg:col-span-4")}
            </div>
            <div className="mt-3">
              <Button size="sm" onClick={() => saveProfile.mutate()} loading={saveProfile.isPending}><Save className="mr-1 h-4 w-4" />Save Profile</Button>
              {!profileReady && <span className="ml-3 text-xs text-amber-600">No profile saved for {taxYear} yet.</span>}
            </div>
          </Card>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="p-4 lg:col-span-3">
              <div className="mb-3 flex items-center gap-2 font-semibold"><FileText className="h-4 w-4" /> I-A. Profit &amp; Loss</div>
              <Table variant="grid"><THead><TR><TH>Line Item</TH><TH className="text-right">Amount</TH></TR></THead><TBody>
                <Row l="Gross Revenue" v={ia.peredaran_usaha} />
                <Row l="Non-Business Income" v={ia.penghasilan_luar_usaha} />
                <Row l="Total Gross Income" v={ia.total_penghasilan_bruto} strong />
                <Row l="Cost of Goods Sold" v={ia.harga_pokok_penjualan} />
                <Row l="Gross Profit" v={ia.laba_kotor_usaha} strong />
                <Row l="Business Expenses" v={ia.biaya_usaha} />
                <Row l="Operating Profit" v={ia.laba_usaha} strong />
                <Row l="Non-Business Expenses" v={ia.biaya_luar_usaha} />
                <Row l="Profit Before Tax (Commercial)" v={ia.laba_sebelum_pajak} strong />
              </TBody></Table>
            </Card>

            <Card className="p-4">
              <div className="mb-3 flex items-center gap-2 font-semibold"><Landmark className="h-4 w-4" /> II. Fiscal Reconciliation</div>
              <Table variant="grid"><THead><TR><TH>Line Item</TH><TH className="text-right">Amount</TH></TR></THead><TBody>
                <Row l="Positive Fiscal Corrections" v={ii.koreksi_fiskal_positif} />
                <Row l="Negative Fiscal Corrections" v={ii.koreksi_fiskal_negatif} />
                <Row l="Fiscal Profit" v={ii.laba_fiskal} strong />
                <TR><TD className="text-slate-600">Loss Carry-forward</TD><TD className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Input type="number" className={input + " h-8 w-32"} value={kompensasi} onChange={(e) => setKompensasi(e.target.value)} />
                  </div>
                </TD></TR>
                <Row l="Taxable Income (PKP)" v={ii.penghasilan_kena_pajak} strong />
              </TBody></Table>
            </Card>

            <Card className="p-4">
              <div className="mb-3 flex items-center gap-2 font-semibold"><FileText className="h-4 w-4" /> III. PPh Computation</div>
              <Table variant="grid"><THead><TR><TH>Line Item</TH><TH className="text-right">Amount</TH></TR></THead><TBody>
                <TR><TD className="text-slate-600">PPh Rate</TD><TD className="text-right">{Number(iii.pph_rate ?? 0) * 100}%</TD></TR>
                <Row l="Tax Payable" v={iii.pph_terutang} strong />
                <Row l="Total Tax Credits" v={iii.total_kredit_pajak} />
                {iii.is_lebih_bayar ? (
                  <Row l="Overpaid Tax" v={iii.pph_lebih_bayar} strong />
                ) : (
                  <Row l="Underpaid Tax" v={iii.pph_kurang_bayar} strong />
                )}
              </TBody></Table>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(iii.kredit_pajak ?? {}).map(([k, v]) => (
                  <Badge key={k}>{k}: {money(v)}</Badge>
                ))}
              </div>
            </Card>
          </div>

          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold"><Landmark className="h-4 w-4" /> Tax Credits</div>
            </div>
            <div className="mb-3 grid gap-2 sm:grid-cols-5">
              <select className={input} value={creditForm.credit_type} onChange={(e) => setCreditForm({ ...creditForm, credit_type: e.target.value })}>
                {CREDIT_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
              <Input type="number" className={input} placeholder="Amount" value={creditForm.amount} onChange={(e) => setCreditForm({ ...creditForm, amount: e.target.value })} />
              <Input type="date" className={input} value={creditForm.payment_date} onChange={(e) => setCreditForm({ ...creditForm, payment_date: e.target.value })} />
              <Input className={input + " sm:col-span-2"} placeholder="Description" value={creditForm.description} onChange={(e) => setCreditForm({ ...creditForm, description: e.target.value })} />
            </div>
            <Button size="sm" onClick={() => addCredit.mutate()} loading={addCredit.isPending} disabled={!creditForm.amount}>Add Credit</Button>
            <Table variant="grid" className="mt-3"><THead><TR><TH>Type</TH><TH>Date</TH><TH>Description</TH><TH className="text-right">Amount</TH><TH /></TR></THead><TBody>
              {(creditsQuery.data ?? []).length === 0 && <TR><TD colSpan={5} className="py-6 text-center text-slate-500">No tax credits recorded.</TD></TR>}
              {(creditsQuery.data ?? []).map((c: any) => (
                <TR key={c.id}>
                  <TD><Badge>{c.credit_type}</Badge></TD>
                  <TD>{c.payment_date || "—"}</TD>
                  <TD>{c.description || "—"}</TD>
                  <TD className="text-right tabular-nums">{money(c.amount)}</TD>
                  <TD><Button size="xs" variant="outline" loading={deleteCredit.isPending && deleteCredit.variables === c.id} onClick={() => deleteCredit.mutate(c.id)}><Trash2 className="h-3 w-3" /></Button></TD>
                </TR>
              ))}
            </TBody></Table>
          </Card>
        </>
      )}
    </div>
  );
}
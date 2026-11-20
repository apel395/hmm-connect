import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/interceptor";
import Button from "@/components/ui/Button";

type AccountOption = { id: number; code: string; name: string };
type PreparationOptions = {
  confirmed_customer: { id: number; code: string; name: string } | null;
  ar_accounts: AccountOption[];
  revenue_accounts: AccountOption[];
  pb1_liability_accounts: AccountOption[];
  accounting_activation_enabled: boolean;
};
type Preview = {
  ready_count: number;
  blocked_count: number;
  balanced: boolean;
  totals: { ar_debit: string; revenue_credit: string; pb1_credit: string };
  posting_enabled: boolean;
  reason: string;
};
const money = (value: string) =>
  "Rp " + Number(value).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ARImportPreparationPanel({
  batchId, onPrepared,
}: { batchId: number; onPrepared: () => void }) {
  const [paymentTermsDays, setPaymentTermsDays] = useState("");
  const [arAccountId, setArAccountId] = useState("");
  const [revenueAccountId, setRevenueAccountId] = useState("");
  const [pb1AccountId, setPb1AccountId] = useState("");
  const [termsConfirmed, setTermsConfirmed] = useState(false);
  const [accountsConfirmed, setAccountsConfirmed] = useState(false);
  const [preparing, setPreparing] = useState(false);

  const options = useQuery({
    queryKey: ["ar-imports", "options"],
    queryFn: async () => (await api.get<PreparationOptions>("/ar-imports/options")).data,
  });
  const preview = useQuery({
    queryKey: ["ar-imports", "journal-preview", batchId],
    queryFn: async () => (await api.get<Preview>("/ar-imports/" + batchId + "/journal-preview")).data,
  });

  const prepare = async () => {
    const customer = options.data?.confirmed_customer;
    if (!customer) return toast.error("Unique active PHR customer is required");
    if (paymentTermsDays.trim() === "" || !Number.isInteger(Number(paymentTermsDays))
      || Number(paymentTermsDays) < 0 || Number(paymentTermsDays) > 365) {
      return toast.error("Enter Finance-approved PHR payment terms (0–365 days)");
    }
    if (!arAccountId || !revenueAccountId || !pb1AccountId) {
      return toast.error("Select AR, Catering revenue and PB-1 liability accounts");
    }
    if (!termsConfirmed || !accountsConfirmed) return toast.error("Confirm payment terms and COA mappings");
    setPreparing(true);
    try {
      const response = await api.post<{ valid_rows: number; error_rows: number }>(
        "/ar-imports/" + batchId + "/prepare", {
          customer_id: customer.id,
          payment_terms_days: Number(paymentTermsDays),
          ar_account_id: Number(arAccountId),
          revenue_account_id: Number(revenueAccountId),
          pb1_liability_account_id: Number(pb1AccountId),
          terms_confirmed: true,
          accounts_confirmed: true,
        },
      );
      await preview.refetch();
      onPrepared();
      setTermsConfirmed(false);
      setAccountsConfirmed(false);
      toast.success(response.data.valid_rows + " invoice(s) prepared. No AR or GL posted.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Preparation failed; no accounting records changed");
    } finally {
      setPreparing(false);
    }
  };

  return (
    <section className="space-y-3 rounded-lg border p-3">
      <div className="text-sm font-semibold">PHR Invoice Preparation — Staging Only</div>
      <p className="text-xs text-slate-600">
        All 229 Catering invoices were confirmed as customer PHR. Verify the contractual
        due-date rule and all posting accounts before preparing. This does not create
        actual AR, sales, journal, General Ledger, or payment records.
      </p>
      {options.isError && <p className="text-xs text-red-700">Could not load customer and chart-of-account choices.</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="text-sm">
          <div className="text-xs text-slate-500">Confirmed customer master</div>
          <strong>{options.data?.confirmed_customer
            ? options.data.confirmed_customer.name + " (" + options.data.confirmed_customer.code + ")"
            : "PHR customer not found or ambiguous"}</strong>
        </div>
        <label className="text-sm">
          PHR payment terms (days from invoice)
          <input type="number" min={0} max={365} step={1} value={paymentTermsDays}
            onChange={e => { setPaymentTermsDays(e.target.value); setTermsConfirmed(false); }}
            className="mt-1 block h-10 w-full rounded border px-3"
            placeholder="From verified contract" />
        </label>
        <label className="text-sm">
          Debit — Piutang Usaha
          <select value={arAccountId} onChange={e => { setArAccountId(e.target.value); setAccountsConfirmed(false); }}
            className="mt-1 block h-10 w-full rounded border px-2">
            <option value="">Select AR account</option>
            {options.data?.ar_accounts.map(a => (
              <option key={a.id} value={a.id}>{a.code} · {a.name}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Credit — Project Catering Revenue
          <select value={revenueAccountId} onChange={e => { setRevenueAccountId(e.target.value); setAccountsConfirmed(false); }}
            className="mt-1 block h-10 w-full rounded border px-2">
            <option value="">Select revenue account</option>
            {options.data?.revenue_accounts.map(a => (
              <option key={a.id} value={a.id}>{a.code} · {a.name}</option>
            ))}
          </select>
        </label>
        <label className="text-sm sm:col-span-2">
          Credit — PB-1 tax liability
          <select value={pb1AccountId} onChange={e => { setPb1AccountId(e.target.value); setAccountsConfirmed(false); }}
            className="mt-1 block h-10 w-full rounded border px-2">
            <option value="">Choose approved PB-1 liability (not PPh23)</option>
            {options.data?.pb1_liability_accounts.map(a => (
              <option key={a.id} value={a.id}>{a.code} · {a.name}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="space-y-2 text-xs">
        <label className="flex items-start gap-2">
          <input type="checkbox" checked={termsConfirmed} onChange={e => setTermsConfirmed(e.target.checked)} />
          I verified that these PHR invoices use the selected payment terms.
        </label>
        <label className="flex items-start gap-2">
          <input type="checkbox" checked={accountsConfirmed} onChange={e => setAccountsConfirmed(e.target.checked)} />
          I verified AR, Catering revenue, and PB-1 liability COA selections.
        </label>
      </div>
      <Button type="button" variant="outline" loading={preparing}
        disabled={preparing || !options.data?.confirmed_customer || !termsConfirmed || !accountsConfirmed}
        onClick={prepare}>Prepare PHR Invoices</Button>

      {preview.data && preview.data.ready_count > 0 && (
        <div className="rounded border p-3 text-sm">
          <div className="mb-2 font-semibold">Proposed accounting journal (not posted)</div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div>Debit AR<strong className="block">{money(preview.data.totals.ar_debit)}</strong></div>
            <div>Credit Revenue<strong className="block">{money(preview.data.totals.revenue_credit)}</strong></div>
            <div>Credit PB-1 Liability<strong className="block">{money(preview.data.totals.pb1_credit)}</strong></div>
          </div>
          <p className="mt-2 text-xs text-slate-600">
            {preview.data.ready_count} prepared, {preview.data.blocked_count} blocked.
            {preview.data.balanced ? " Journal preview balanced." : " Journal preview unbalanced."}
            {" "}No GL, payment, PPh23, or AR record was created.
          </p>
        </div>
      )}
    </section>
  );
}

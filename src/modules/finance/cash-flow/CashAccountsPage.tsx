import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { filterBusinessUnits, listLocations } from "@/modules/admin/organization/api";
import { getCashAccounts } from "./api";
import { BankAccount, listBankAccounts, saveBankAccount } from "./bankAccountApi";

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const empty = { bank_name: "", account_name: "", account_number: "", account_holder: "", currency: "IDR", business_unit_id: 0, location_id: null as number | null, coa_account_id: 0, is_active: true };

export default function CashAccountsPage() {
  const nav = useNavigate();
  const queryClient = useQueryClient();
  const [dates, setDates] = useState({ date_from: "", date_to: "" });
  const [form, setForm] = useState<any>(empty);
  const activity = useQuery({ queryKey: ["cash-accounts", dates], queryFn: () => getCashAccounts(dates) });
  const bankAccounts = useQuery({ queryKey: ["bank-accounts"], queryFn: () => listBankAccounts(false) });
  const businessUnits = useQuery({ queryKey: ["business-units", "bank-account", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const locations = useQuery({ queryKey: ["bank-account-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: form.business_unit_id, is_active: true }), enabled: Boolean(form.business_unit_id) });
  const coa = useQuery({ queryKey: ["bank-coa"], queryFn: () => getAccountLookup({ account_type: "ASSET", is_posting: true, is_active: true }) });

  useEffect(() => {
    if (!form.id && !form.business_unit_id && businessUnits.data?.length === 1) {
      setForm((current: any) => ({ ...current, business_unit_id: businessUnits.data![0].id }));
    }
  }, [businessUnits.data, form.id, form.business_unit_id]);

  const save = useMutation({
    mutationFn: () => saveBankAccount(form),
    onSuccess: () => {
      toast.success(form.id ? "Bank account updated" : "Bank account created");
      setForm({ ...empty, business_unit_id: businessUnits.data?.length === 1 ? businessUnits.data[0].id : 0 });
      queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || "Bank account could not be saved"),
  });

  const submit = () => {
    if (!form.bank_name?.trim()) return toast.error("Bank Name is required");
    if (!form.account_name?.trim()) return toast.error("Account Name is required");
    if (!form.account_number?.trim()) return toast.error("Account Number is required");
    if (!form.business_unit_id) return toast.error("Select a Business Unit before saving the bank account");
    if (!form.coa_account_id) return toast.error("Select a Linked COA before saving the bank account");
    save.mutate();
  };

  const edit = (row: BankAccount) => setForm({ ...row, location_id: row.location_id ?? null });
  const canSave = Boolean(form.bank_name?.trim() && form.account_name?.trim() && form.account_number?.trim() && form.business_unit_id && form.coa_account_id);

  return <div className="space-y-6">
    <PageHeader title="Cash & Bank Accounts" description="Register real bank accounts, link each account to its posting COA, and review posted cash activity." />

    <Card className="space-y-4">
      <div><h2 className="text-lg font-semibold">Bank Account Master</h2><p className="text-sm text-slate-500">Each physical bank account must link to a unique cash/bank COA. Fields marked * are required.</p></div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">Bank Name *<input className={input} value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} /></label>
        <label className="text-sm">Account Name *<input className={input} value={form.account_name} onChange={(e) => setForm({ ...form, account_name: e.target.value })} /></label>
        <label className="text-sm">Account Number *<input className={input} value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} /></label>
        <label className="text-sm">Account Holder<input className={input} value={form.account_holder ?? ""} onChange={(e) => setForm({ ...form, account_holder: e.target.value })} /></label>
        <label className="text-sm">Currency<input className={input} maxLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} /></label>
        <label className="text-sm">Business Unit *<select required className={input} value={form.business_unit_id || ""} onChange={(e) => setForm({ ...form, business_unit_id: Number(e.target.value), location_id: null })}><option value="">Select Business Unit</option>{businessUnits.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm">Location<select disabled={!form.business_unit_id} className={input} value={form.location_id ?? ""} onChange={(e) => setForm({ ...form, location_id: Number(e.target.value) || null })}><option value="">Optional</option>{locations.data?.map((row: any) => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label>
        <label className="text-sm md:col-span-2">Linked COA *<select required className={input} value={form.coa_account_id || ""} onChange={(e) => setForm({ ...form, coa_account_id: Number(e.target.value) })}><option value="">Select bank/cash posting account</option>{coa.data?.map((row: any) => <option key={row.id} value={row.id}>{row.account_code} — {row.account_name}</option>)}</select></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />Active</label>
      </div>
      <div className="flex justify-end gap-2">{form.id && <Button variant="outline" onClick={() => setForm({ ...empty, business_unit_id: businessUnits.data?.length === 1 ? businessUnits.data[0].id : 0 })}>Cancel Edit</Button>}<Button loading={save.isPending} disabled={!canSave} onClick={submit}>{form.id ? "Update Bank Account" : "Create Bank Account"}</Button></div>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="text-left">Bank</th><th>Account</th><th>Number</th><th>Business Unit</th><th>Location</th><th>Linked COA</th><th>Status</th><th>Action</th></tr></thead><tbody>{bankAccounts.data?.map((row) => <tr key={row.id} className="border-t"><td>{row.bank_name}</td><td>{row.account_name}</td><td>{row.account_number}</td><td>{row.business_unit_name ?? "—"}</td><td>{row.location_name ?? "—"}</td><td>{row.coa_account_code} — {row.coa_account_name}</td><td>{row.is_active ? "Active" : "Inactive"}</td><td><Button size="xs" variant="outline" onClick={() => edit(row)}>Edit</Button></td></tr>)}</tbody></table></div>
    </Card>

    <Card className="space-y-4">
      <div><h2 className="text-lg font-semibold">Posted Cash & Bank Activity</h2><p className="text-sm text-slate-500">Balances below are derived from posted accounting transactions.</p></div>
      <div className="flex gap-3"><input type="date" className={input} onChange={(e) => setDates({ ...dates, date_from: e.target.value })} /><input type="date" className={input} onChange={(e) => setDates({ ...dates, date_to: e.target.value })} /></div>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Code</th><th>Name</th><th>Subtype</th><th>Opening</th><th>Inflow</th><th>Outflow</th><th>Closing</th><th>Last Activity</th><th>Action</th></tr></thead><tbody>{activity.data?.map((row: any) => <tr key={row.account_id} className="border-t"><td>{row.account_code}</td><td>{row.account_name}</td><td>{row.account_subtype}</td><td>{money(row.opening_balance)}</td><td>{money(row.total_inflow)}</td><td>{money(row.total_outflow)}</td><td>{money(row.closing_balance)}</td><td>{row.last_transaction_date || "—"}</td><td><button className="text-emerald-700" onClick={() => nav(`/cash-accounts/${row.account_id}`)}>View</button></td></tr>)}</tbody></table></div>
    </Card>
  </div>;
}

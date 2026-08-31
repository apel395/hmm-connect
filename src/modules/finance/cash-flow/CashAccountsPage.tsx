import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import SearchableSelect from "@/components/form/SearchableSelect";
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
  const formRef = useRef<HTMLDivElement | null>(null);
  const activity = useQuery({ queryKey: ["cash-accounts", dates], queryFn: () => getCashAccounts(dates) });
  const bankAccounts = useQuery({ queryKey: ["bank-accounts"], queryFn: () => listBankAccounts(false) });
  const businessUnits = useQuery({ queryKey: ["business-units", "bank-account", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const locations = useQuery({ queryKey: ["bank-account-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: form.business_unit_id, is_active: true }), enabled: Boolean(form.business_unit_id) });
  const coa = useQuery({ queryKey: ["bank-coa"], queryFn: () => getAccountLookup({ account_type: "ASSET", is_posting: true, is_active: true, page: 1, page_size: 1000 }) });

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

  const edit = (row: BankAccount) => {
    setForm({ ...row, location_id: row.location_id ?? null });
    requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };
  const canSave = Boolean(form.bank_name?.trim() && form.account_name?.trim() && form.account_number?.trim() && form.business_unit_id && form.coa_account_id);
  const businessUnitOptions=(businessUnits.data??[]).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}));
  const locationOptions=(locations.data??[]).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}));
  const coaOptions=(coa.data??[]).map((row:any)=>({id:row.id,label:`${row.account_code} — ${row.account_name}`,keywords:[row.account_code,row.account_name,row.account_type]}));

  return <div className="space-y-6">
    <PageHeader title="Cash & Bank Accounts" description="Register real bank accounts, link each account to its posting COA, and review posted cash activity." />

    <Card className="space-y-4">
      <div ref={formRef} className="scroll-mt-28" />
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Bank Account Master</h2><p className="text-sm text-slate-500">Each physical bank account must link to a unique cash/bank COA. Leave Location as Global / all locations for a corporate funding account usable by every location in the Business Unit.</p></div>{form.id && <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-800">Editing: {form.bank_name} — {form.account_name}</div>}</div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">Bank Name *<input className={input} value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} /></label>
        <label className="text-sm">Account Name *<input className={input} value={form.account_name} onChange={(e) => setForm({ ...form, account_name: e.target.value })} /></label>
        <label className="text-sm">Account Number *<input className={input} value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} /></label>
        <label className="text-sm">Account Holder<input className={input} value={form.account_holder ?? ""} onChange={(e) => setForm({ ...form, account_holder: e.target.value })} /></label>
        <label className="text-sm">Currency<input className={input} maxLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} /></label>
        <SearchableSelect label="Business Unit" value={form.business_unit_id || undefined} required disabled={businessUnits.isLoading} placeholder="Type business unit..." options={businessUnitOptions} onChange={(value)=>setForm({ ...form, business_unit_id:value ?? 0, location_id:null })} />
        <SearchableSelect label="Location" value={form.location_id ?? undefined} disabled={!form.business_unit_id || locations.isLoading} placeholder="Type location..." options={locationOptions} onChange={(value)=>setForm({ ...form, location_id:value ?? null })} />
        <div className="md:col-span-2"><SearchableSelect label="Linked COA" value={form.coa_account_id || undefined} required disabled={coa.isLoading} placeholder="Type COA code or account name..." options={coaOptions} onChange={(value)=>setForm({ ...form, coa_account_id:value ?? 0 })} /></div>
        <label className="flex items-center gap-2 text-sm pt-6"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />Active</label>
      </div>
      <div className="flex justify-end gap-2">{form.id && <Button variant="outline" onClick={() => setForm({ ...empty, business_unit_id: businessUnits.data?.length === 1 ? businessUnits.data[0].id : 0 })}>Cancel Edit</Button>}<Button loading={save.isPending} disabled={!canSave} onClick={submit}>{form.id ? "Update Bank Account" : "Create Bank Account"}</Button></div>
      <Table className="min-w-[780px]"><THead><TR className="whitespace-nowrap"><TH>Bank Account</TH><TH>Organization</TH><TH>Linked COA</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead><TBody>{bankAccounts.data?.map((row) => <TR key={row.id} className="whitespace-nowrap"><TD><TableCellStack primary={`${row.bank_name} — ${row.account_name}`} secondary={row.account_number}/></TD><TD><TableCellStack primary={row.business_unit_name ?? "—"} secondary={row.location_name ?? undefined}/></TD><TD><TableCellStack primary={row.coa_account_name} secondary={row.coa_account_code}/></TD><TD>{row.is_active ? "Active" : "Inactive"}</TD><TD><div className="flex justify-end"><Button size="xs" variant="outline" onClick={() => edit(row)}>Edit</Button></div></TD></TR>)}</TBody></Table>
    </Card>

    <Card className="space-y-4">
      <div><h2 className="text-lg font-semibold">Posted Cash & Bank Activity</h2><p className="text-sm text-slate-500">Balances below are derived from posted accounting transactions.</p></div>
      <div className="flex gap-3"><input type="date" className={input} onChange={(e) => setDates({ ...dates, date_from: e.target.value })} /><input type="date" className={input} onChange={(e) => setDates({ ...dates, date_to: e.target.value })} /></div>
      <Table className="min-w-[850px]"><THead><TR className="whitespace-nowrap"><TH>Account</TH><TH numeric>Opening</TH><TH numeric>Inflow</TH><TH numeric>Outflow</TH><TH numeric>Closing</TH><TH>Last Activity</TH><TH numeric>Action</TH></TR></THead><TBody>{activity.data?.map((row: any) => <TR key={row.account_id} className="whitespace-nowrap"><TD><TableCellStack primary={row.account_name} secondary={`${row.account_code} · ${row.account_subtype}`}/></TD><TD numeric>{money(row.opening_balance)}</TD><TD numeric>{money(row.total_inflow)}</TD><TD numeric>{money(row.total_outflow)}</TD><TD numeric className="font-semibold">{money(row.closing_balance)}</TD><TD>{row.last_transaction_date || "—"}</TD><TD><div className="flex justify-end"><button className="font-medium text-emerald-700 hover:underline" onClick={() => nav(`/cash-accounts/${row.account_id}`)}>View</button></div></TD></TR>)}</TBody></Table>
    </Card>
  </div>;
}

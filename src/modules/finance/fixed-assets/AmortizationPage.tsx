import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {Plus, Printer} from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import CurrencyInput from "@/components/form/CurrencyInput";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { createAmortization, listAmortizations, postNextAmortization } from "./api";

const today = new Date().toISOString().slice(0, 10);
const inputClass = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const blankForm = () => ({ name: "", category: "", start_date: today, original_cost: 0, useful_life_months: 12, business_unit_id: "", location_id: "", department_id: "", asset_account_id: "", accumulated_amortization_account_id: "", amortization_expense_account_id: "", notes: "" });

export default function AmortizationPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<any>(blankForm());

  const records = useQuery({ queryKey: ["amortizations"], queryFn: listAmortizations });
  const businessUnits = useQuery({ queryKey: ["business-units", "amortization", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const locations = useQuery({ queryKey: ["amortization-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const departments = useQuery({ queryKey: ["amortization-departments", form.business_unit_id], queryFn: () => listDepartments({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const accounts = useQuery({ queryKey: ["amortization-accounts"], queryFn: () => getAccountLookup({ is_active: true, is_posting: true }) });

  useEffect(() => {
    if (!form.business_unit_id && businessUnits.data?.length === 1) setForm((current: any) => ({ ...current, business_unit_id: String(businessUnits.data![0].id) }));
  }, [businessUnits.data, form.business_unit_id]);

  const payload = () => ({
    ...form,
    original_cost: Number(form.original_cost),
    useful_life_months: Number(form.useful_life_months),
    business_unit_id: Number(form.business_unit_id),
    location_id: form.location_id ? Number(form.location_id) : null,
    department_id: form.department_id ? Number(form.department_id) : null,
    asset_account_id: Number(form.asset_account_id),
    accumulated_amortization_account_id: Number(form.accumulated_amortization_account_id),
    amortization_expense_account_id: Number(form.amortization_expense_account_id),
    category: form.category || null,
    notes: form.notes || null,
  });

  const save = useMutation({
    mutationFn: () => createAmortization(payload()),
    onSuccess: () => {
      toast.success("Amortization record created");
      queryClient.invalidateQueries({ queryKey: ["amortizations"] });
      setShowForm(false);
      setForm({ ...blankForm(), business_unit_id: businessUnits.data?.length === 1 ? String(businessUnits.data[0].id) : "" });
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Amortization record could not be saved"),
  });
  const post = useMutation({ mutationFn: postNextAmortization, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["amortizations"] }) });

  const submit = () => {
    if (!form.name.trim()) return toast.error("Name is required");
    if (!(Number(form.original_cost) > 0)) return toast.error("Original Cost must be greater than zero");
    if (!(Number(form.useful_life_months) > 0)) return toast.error("Useful Life must be greater than zero");
    if (!form.business_unit_id) return toast.error("Select a Business Unit for this amortization record");
    if (!form.asset_account_id || !form.accumulated_amortization_account_id || !form.amortization_expense_account_id) return toast.error("Complete all required amortization posting accounts");
    save.mutate();
  };

  const totalNetBookValue = useMemo(() => (records.data ?? []).reduce((sum: number, item: any) => sum + Number(item.net_book_value || 0), 0), [records.data]);
  const set = (key: string, value: any) => setForm((current: any) => ({ ...current, [key]: value }));
  const accountSelect = (key: string) => <select className={inputClass} value={form[key]} onChange={(event) => set(key, event.target.value)}><option value="">Select account</option>{(accounts.data ?? []).map((account: any) => <option key={account.id} value={account.id}>{account.account_number} — {account.account_name}</option>)}</select>;

  return <div className="space-y-5">
    <PageHeader title="Amortization" description="Manage straight-line amortization for intangible assets and other amortizable costs." actions={<>
<Button onClick={() => setShowForm((value) => !value)}><Plus size={16}/> New Amortization</Button>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>} />
    <div className="grid gap-3 md:grid-cols-3"><Card className="p-4"><div className="text-xs uppercase text-slate-500">Active Records</div><div className="mt-2 text-2xl font-semibold">{(records.data ?? []).filter((x: any) => x.status === "ACTIVE").length}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Total Net Book Value</div><div className="mt-2 text-2xl font-semibold">{totalNetBookValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Method</div><div className="mt-2 text-lg font-semibold">Straight Line</div></Card></div>

    {showForm && <Card className="grid gap-4 p-5 md:grid-cols-3">
      <label className="text-sm font-medium">Name *<input className={`${inputClass} mt-1`} value={form.name} onChange={(event) => set("name", event.target.value)}/></label>
      <label className="text-sm font-medium">Category<input className={`${inputClass} mt-1`} placeholder="Software, license, prepaid cost..." value={form.category} onChange={(event) => set("category", event.target.value)}/></label>
      <label className="text-sm font-medium">Start Date *<input type="date" className={`${inputClass} mt-1`} value={form.start_date} onChange={(event) => set("start_date", event.target.value)}/></label>
      <label className="text-sm font-medium">Original Cost *<div className="mt-1"><CurrencyInput value={Number(form.original_cost)} onValueChange={(value) => set("original_cost", value)}/></div></label>
      <label className="text-sm font-medium">Useful Life (Months) *<input type="number" min={1} className={`${inputClass} mt-1`} value={form.useful_life_months} onChange={(event) => set("useful_life_months", Number(event.target.value))}/></label>
      <label className="text-sm font-medium">Business Unit *<select required className={`${inputClass} mt-1`} value={form.business_unit_id} onChange={(event) => setForm((current: any) => ({ ...current, business_unit_id: event.target.value, location_id: "", department_id: "" }))}><option value="">Select business unit</option>{(businessUnits.data ?? []).map((item: any) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
      <label className="text-sm font-medium">Location<select disabled={!form.business_unit_id} className={`${inputClass} mt-1`} value={form.location_id} onChange={(event) => set("location_id", event.target.value)}><option value="">Optional</option>{(locations.data ?? []).map((item: any) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
      <label className="text-sm font-medium">Department<select disabled={!form.business_unit_id} className={`${inputClass} mt-1`} value={form.department_id} onChange={(event) => set("department_id", event.target.value)}><option value="">Optional</option>{(departments.data ?? []).map((item: any) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
      <div />
      <label className="text-sm font-medium">Amortizable Asset Account *<div className="mt-1">{accountSelect("asset_account_id")}</div></label>
      <label className="text-sm font-medium">Accumulated Amortization *<div className="mt-1">{accountSelect("accumulated_amortization_account_id")}</div></label>
      <label className="text-sm font-medium">Amortization Expense *<div className="mt-1">{accountSelect("amortization_expense_account_id")}</div></label>
      <label className="text-sm font-medium md:col-span-3">Notes<textarea className="mt-1 min-h-20 w-full rounded-md border border-slate-300 p-3" value={form.notes} onChange={(event) => set("notes", event.target.value)}/></label>
      <div className="md:col-span-3 flex justify-end gap-2"><Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button><Button loading={save.isPending} onClick={submit}>Save</Button></div>
    </Card>}

    <Card className="overflow-x-auto p-0"><table className="w-full min-w-[1100px] text-sm"><thead><tr className="border-b bg-slate-50 text-left"><th className="p-3">Number</th><th>Name</th><th>Category</th><th>Start</th><th className="text-right">Original Cost</th><th className="text-right">Monthly</th><th>Progress</th><th className="text-right">Accumulated</th><th className="text-right">Net Book Value</th><th>Status</th><th className="p-3 text-right">Action</th></tr></thead><tbody>{(records.data ?? []).map((item: any) => <tr key={item.id} className="border-b"><td className="p-3 font-medium">{item.amortization_number}</td><td>{item.name}</td><td>{item.category || "—"}</td><td>{item.start_date}</td><td className="text-right tabular-nums">{Number(item.original_cost).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td className="text-right tabular-nums">{Number(item.monthly_amortization).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td>{item.months_posted}/{item.useful_life_months} months</td><td className="text-right tabular-nums">{Number(item.accumulated_amortization).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td className="text-right tabular-nums">{Number(item.net_book_value).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td><Badge variant={item.status === "ACTIVE" ? "success" : "secondary"}>{item.status}</Badge></td><td className="p-3 text-right">{item.can_post_next && <Button size="sm" loading={post.isPending} onClick={() => post.mutate(item.id)}>Post Next Month</Button>}</td></tr>)}</tbody></table>{!records.isLoading && !(records.data ?? []).length && <div className="p-10 text-center text-sm text-slate-500">No amortization records.</div>}</Card>
  </div>;
}

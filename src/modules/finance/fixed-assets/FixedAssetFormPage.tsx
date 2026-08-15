import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { filterBusinessUnits, listLocations, listDepartments } from "@/modules/admin/organization/api";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { isBeforeToday, todayLocal } from "@/utils/dateConstraints";
import { createAsset, listCategories } from "./api";

const input = "h-9 rounded border px-2 text-sm";

export default function FixedAssetFormPage() {
  const nav = useNavigate();
  const [f, setF] = useState<any>({
    asset_name: "", asset_category_id: "", acquisition_date: todayLocal(), acquisition_cost: "", residual_value: "0",
    useful_life_months: 60, depreciation_method: "STRAIGHT_LINE", business_unit_id: "", location_id: "",
    department_id: "", asset_account_id: "", accumulated_depreciation_account_id: "",
    depreciation_expense_account_id: "", source_type: "MANUAL", notes: "",
  });
  const cats = useQuery({ queryKey: ["asset-categories"], queryFn: listCategories });
  const bus = useQuery({ queryKey: ["business-units", "fixed-asset", "active"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const loc = useQuery({ queryKey: ["asset-locations", f.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(f.business_unit_id), is_active: true }), enabled: Boolean(f.business_unit_id) });
  const dep = useQuery({ queryKey: ["asset-departments", f.business_unit_id], queryFn: () => listDepartments({ business_unit_id: Number(f.business_unit_id), is_active: true }), enabled: Boolean(f.business_unit_id) });
  const accounts = useQuery({ queryKey: ["asset-accounts"], queryFn: () => getAccountLookup({ is_active: true, is_posting: true }) });

  useEffect(() => {
    if (!f.business_unit_id && bus.data?.length === 1) setF((current: any) => ({ ...current, business_unit_id: String(bus.data![0].id) }));
  }, [bus.data, f.business_unit_id]);

  const set = (k: string, v: any) => setF((current: any) => ({ ...current, [k]: v }));
  const account = (k: string) => <select className={input} value={f[k]} onChange={(e) => set(k, e.target.value)}><option value="">Select account</option>{accounts.data?.map((a: any) => <option key={a.id} value={a.id}>{a.account_number} — {a.account_name}</option>)}</select>;

  const save = async () => {
    if (!f.asset_name.trim()) return toast.error("Asset Name is required");
    if (!f.asset_category_id) return toast.error("Select an Asset Category");
    if (!f.acquisition_date || isBeforeToday(f.acquisition_date)) return toast.error("Acquisition Date cannot be before today");
    if (!(Number(f.acquisition_cost) > 0)) return toast.error("Acquisition Cost must be greater than zero");
    if (!f.business_unit_id) return toast.error("Select a Business Unit for this asset");
    if (!f.asset_account_id || !f.accumulated_depreciation_account_id || !f.depreciation_expense_account_id) return toast.error("Complete all required asset posting accounts");

    const ids = ["asset_category_id", "business_unit_id", "location_id", "department_id", "asset_account_id", "accumulated_depreciation_account_id", "depreciation_expense_account_id"];
    const data = { ...f, acquisition_cost: Number(f.acquisition_cost), residual_value: Number(f.residual_value), useful_life_months: Number(f.useful_life_months), ...Object.fromEntries(ids.map((k) => [k, f[k] ? Number(f[k]) : null])) };
    try { const x = await createAsset(data); nav(`/fixed-assets/${x.id}`); } catch (error: any) { toast.error(error?.response?.data?.detail || "Fixed asset could not be saved"); }
  };

  return <div className="space-y-4">
    <PageHeader title="New Fixed Asset" description="Register an asset as draft before capitalization." actions={<Button variant="outline" onClick={() => nav("/fixed-assets")}>Back</Button>} />
    <Card className="grid gap-3 p-4 md:grid-cols-3">
      <label>Asset Name *<input className={`${input} block w-full`} value={f.asset_name} onChange={(e) => set("asset_name", e.target.value)} /></label>
      <label>Category *<select className={`${input} block w-full`} value={f.asset_category_id} onChange={(e) => { const c = cats.data?.find((x: any) => x.id === Number(e.target.value)); setF({ ...f, asset_category_id: e.target.value, useful_life_months: c?.default_useful_life_months || f.useful_life_months, asset_account_id: c?.asset_account_id || "", accumulated_depreciation_account_id: c?.accumulated_depreciation_account_id || "", depreciation_expense_account_id: c?.depreciation_expense_account_id || "", disposal_gain_account_id: c?.disposal_gain_account_id || null, disposal_loss_account_id: c?.disposal_loss_account_id || null }); }}><option value="">Select</option>{cats.data?.map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      <label>Acquisition Date *<input className={`${input} block w-full`} type="date" min={todayLocal()} value={f.acquisition_date} onChange={(e) => set("acquisition_date", e.target.value)} /></label>
      <label>Acquisition Cost *<input className={`${input} block w-full text-right`} type="number" min={0} value={f.acquisition_cost} onChange={(e) => set("acquisition_cost", e.target.value)} /></label>
      <label>Residual Value<input className={`${input} block w-full text-right`} type="number" min={0} value={f.residual_value} onChange={(e) => set("residual_value", e.target.value)} /></label>
      <label>Useful Life Months *<input className={`${input} block w-full`} type="number" min={1} value={f.useful_life_months} onChange={(e) => set("useful_life_months", e.target.value)} /></label>
      <label>Business Unit *<select required className={`${input} block w-full`} value={f.business_unit_id} onChange={(e) => setF({ ...f, business_unit_id: e.target.value, location_id: "", department_id: "" })}><option value="">Select business unit</option>{bus.data?.map((x: any) => <option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <label>Location<select disabled={!f.business_unit_id} className={`${input} block w-full`} value={f.location_id} onChange={(e) => set("location_id", e.target.value)}><option value="">Optional</option>{loc.data?.map((x: any) => <option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <label>Department<select disabled={!f.business_unit_id} className={`${input} block w-full`} value={f.department_id} onChange={(e) => set("department_id", e.target.value)}><option value="">Optional</option>{dep.data?.map((x: any) => <option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <label>Asset Account *{account("asset_account_id")}</label>
      <label>Accumulated Depreciation *{account("accumulated_depreciation_account_id")}</label>
      <label>Depreciation Expense *{account("depreciation_expense_account_id")}</label>
      <label className="md:col-span-3">Notes<input className={`${input} block w-full`} value={f.notes} onChange={(e) => set("notes", e.target.value)} /></label>
      <div className="md:col-span-3 text-right"><Button onClick={save}>Save Draft</Button></div>
    </Card>
  </div>;
}
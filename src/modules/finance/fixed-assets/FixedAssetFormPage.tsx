import {
  categoryDefaults,
  postingDefaults,
  groupAcceptsAccount,
} from "./categoryRules";
import {
  fixedAssetAccount,
  accumulatedDepreciationAccount,
  depreciationExpenseAccount,
} from "./accountRules";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import {
  filterBusinessUnits,
  listDepartments,
  listLocations,
} from "@/modules/admin/organization/api";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { todayLocal } from "@/utils/dateConstraints";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  CalendarRange,
  Info,
  LockKeyhole,
  MapPin,
  Package,
  Printer,
  Save,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { assetAction, createAsset, getAsset, listCategories } from "./api";

const input =
  "block h-9 w-full min-w-0 rounded-md border border-slate-300 bg-white px-2.5 text-sm text-slate-900 disabled:bg-slate-50 disabled:text-slate-600";
const field = "flex min-w-0 flex-col gap-1 text-sm text-slate-600";
const section = "border-b border-slate-200 p-4 sm:px-5";
const grid = "grid gap-3 sm:grid-cols-2 lg:grid-cols-3";
const heading =
  "mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900";
const categoryNotes: Record<string, string> = {
  GROUP_1: "Contoh: komputer, printer, peralatan kantor kecil.",
  GROUP_2: "Contoh: furnitur logam, AC, kendaraan operasional tertentu.",
  GROUP_3: "Mesin dan peralatan industri tertentu sesuai jenis usaha.",
  GROUP_4: "Aset industri khusus dengan masa manfaat fiskal 240 bulan.",
  BUILDING_PERMANENT: "Bangunan permanen.",
  BUILDING_NON_PERMANENT: "Bangunan tidak permanen.",
  LAND: "Tanah tidak disusutkan.",
};

export default function FixedAssetFormPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const registrationId = Number(params.get("registration_id")) || undefined;
  const registration = useQuery({
    queryKey: ["fixed-asset", registrationId],
    queryFn: () => getAsset(registrationId!),
    refetchOnWindowFocus: false,
    enabled: Boolean(registrationId),
  });
  const [f, setF] = useState<any>({
    asset_name: "",
    asset_category_id: "",
    acquisition_date: registrationId ? "" : todayLocal(),
    acquisition_cost: "",
    residual_value: "0",
    accumulated_depreciation: "0",
    quantity: "",
    useful_life_months: 48,
    depreciation_method: "STRAIGHT_LINE",
    business_unit_id: "",
    location_id: "",
    department_id: "",
    asset_account_id: "",
    accumulated_depreciation_account_id: "",
    depreciation_expense_account_id: "",
    source_type: "MANUAL",
    notes: "",
  });
  useEffect(() => {
    if (registration.data?.status === "PENDING_REGISTRATION") {
      const asset = registration.data;
      setF((current: any) => ({
        ...current,
        asset_name: asset.asset_name,
        product_id: asset.product_id,
        asset_account_id: asset.asset_account_id,
        business_unit_id: asset.business_unit_id || "",
        source_type: "ITEM_MASTER",
      }));
    }
  }, [registration.data]);
  const cats = useQuery({
    queryKey: ["asset-categories"],
    queryFn: listCategories,
  });
  const bus = useQuery({
    queryKey: ["business-units", "fixed-asset", "active"],
    queryFn: () => filterBusinessUnits({ is_active: true }),
  });
  const loc = useQuery({
    queryKey: ["asset-locations", f.business_unit_id],
    queryFn: () =>
      listLocations({
        business_unit_id: Number(f.business_unit_id),
        is_active: true,
      }),
    enabled: Boolean(f.business_unit_id),
  });
  const dep = useQuery({
    queryKey: ["asset-departments", f.business_unit_id, f.location_id],
    queryFn: () =>
      listDepartments({
        business_unit_id: Number(f.business_unit_id),
        location_id: Number(f.location_id) || undefined,
        is_active: true,
      }),
    enabled: Boolean(f.business_unit_id),
  });
  const accounts = useQuery({
    queryKey: ["asset-accounts"],
    queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }),
  });

  useEffect(() => {
    if (!f.business_unit_id && bus.data?.length === 1)
      setF((current: any) => ({
        ...current,
        business_unit_id: String(bus.data![0].id),
      }));
  }, [bus.data, f.business_unit_id]);

  const set = (k: string, v: any) =>
    setF((current: any) => ({ ...current, [k]: v }));
  const selectedCategory = cats.data?.find(
    (c: any) => c.id === Number(f.asset_category_id),
  );
  const account = (k: string) => (
    <select
      disabled={Boolean(registrationId && k === "asset_account_id")}
      aria-label={
        k === "asset_account_id"
          ? "Asset Account"
          : k === "accumulated_depreciation_account_id"
            ? "Accumulated Depreciation"
            : "Depreciation Expense"
      }
      className={input}
      value={f[k]}
      onChange={(e) =>
        k === "asset_account_id"
          ? setF({
              ...f,
              ...postingDefaults(
                e.target.value,
                f.depreciation_method !== "NONE",
                accounts.data ?? [],
              ),
            })
          : set(k, e.target.value)
      }
    >
      <option value="">Select account</option>
      {accounts.data
        ?.filter(
          k === "asset_account_id"
            ? (a: any) =>
                fixedAssetAccount(a) &&
                groupAcceptsAccount(
                  selectedCategory?.fiscal_group_code,
                  a.account_code,
                )
            : k === "accumulated_depreciation_account_id"
              ? accumulatedDepreciationAccount
              : depreciationExpenseAccount,
        )
        .map((a: any) => (
          <option key={a.id} value={a.id}>
            {a.account_code} — {a.account_name}
          </option>
        ))}
    </select>
  );

  const save = async () => {
    if (registrationId && registration.data?.status !== "PENDING_REGISTRATION")
      return toast.error("Pending registration is required");
    if (!f.asset_name.trim()) return toast.error("Asset Name is required");
    if (!f.asset_category_id) return toast.error("Select an Asset Category");
    if (!f.acquisition_date) return toast.error("Acquisition Date is required");
    if (!(Number(f.acquisition_cost) > 0))
      return toast.error("Acquisition Cost must be greater than zero");
    if (!f.business_unit_id)
      return toast.error("Select a Business Unit for this asset");
    if (
      !f.asset_account_id ||
      (f.depreciation_method !== "NONE" &&
        (!f.accumulated_depreciation_account_id ||
          !f.depreciation_expense_account_id))
    )
      return toast.error("Complete all required asset posting accounts");

    const ids = [
      "asset_category_id",
      "business_unit_id",
      "location_id",
      "department_id",
      "asset_account_id",
      "accumulated_depreciation_account_id",
      "depreciation_expense_account_id",
    ];
    const data = {
      ...f,
      acquisition_cost: Number(f.acquisition_cost),
      residual_value: Number(f.residual_value),
      accumulated_depreciation: Number(f.accumulated_depreciation),
      quantity: f.quantity ? Number(f.quantity) : null,
      useful_life_months:
        f.depreciation_method === "NONE" ? null : Number(f.useful_life_months),
      ...Object.fromEntries(ids.map((k) => [k, f[k] ? Number(f[k]) : null])),
    };
    try {
      const x = registrationId
        ? await assetAction(registrationId, "complete-registration", data)
        : await createAsset(data);
      nav(`/fixed-assets/${x.id}`);
    } catch (error: any) {
      toast.error(
        error?.response?.data?.detail || "Fixed asset could not be saved",
      );
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title={
          registrationId ? "Complete Asset Registration" : "New Fixed Asset"
        }
        description="Register an asset as draft before capitalization."
        actions={
          <>
            <WorkspaceBackButton />
            <Button variant="outline" onClick={() => window.print()}>
              <Printer size={16} /> Print
            </Button>
          </>
        }
      />
      <Card className="overflow-hidden">
        <section className={section} aria-labelledby="asset-details-heading">
          <h2 id="asset-details-heading" className={heading}>
            <Package
              size={16}
              className="text-emerald-700"
              aria-hidden="true"
            />
            Asset details
          </h2>
          <div className={grid}>
            <label className={`${field} sm:col-span-2`}>
              Asset Name *
              <input
                className={`${input}`}
                value={f.asset_name}
                onChange={(e) => set("asset_name", e.target.value)}
              />
            </label>
            <label className={field}>
              Acquisition Date *
              <input
                className={`${input}`}
                type="date"
                data-accounting-date="true"
                value={f.acquisition_date}
                onChange={(e) => set("acquisition_date", e.target.value)}
              />
            </label>
            <label className={field}>
              Acquisition Cost *
              <input
                className={`${input} text-right`}
                type="number"
                min={0}
                value={f.acquisition_cost}
                onChange={(e) => set("acquisition_cost", e.target.value)}
              />
            </label>
            {f.depreciation_method !== "NONE" && (
              <label className={field}>
                Opening Accumulated Depreciation
                <input
                  className={`${input} text-right`}
                  type="number"
                  min={0}
                  step="0.01"
                  value={f.accumulated_depreciation}
                  onChange={(e) =>
                    set("accumulated_depreciation", e.target.value)
                  }
                />
              </label>
            )}
            <label className={field}>
              Residual Value
              <input
                className={`${input} text-right`}
                type="number"
                min={0}
                value={f.residual_value}
                onChange={(e) => set("residual_value", e.target.value)}
              />
            </label>
            <label className={field}>
              Quantity
              <input
                className={`${input}`}
                type="number"
                min={0.0001}
                step="any"
                value={f.quantity}
                onChange={(e) => set("quantity", e.target.value)}
              />
            </label>
          </div>
        </section>
        <section className={section} aria-labelledby="asset-category-heading">
          <h2 id="asset-category-heading" className={heading}>
            <CalendarRange
              size={16}
              className="text-emerald-700"
              aria-hidden="true"
            />
            Category &amp; useful life
          </h2>
          <div className={grid}>
            <div className="min-w-0 sm:col-span-2">
              <label className={field}>
                Fiscal Category *
                <select
                  className={`${input}`}
                  aria-describedby={
                    selectedCategory ? "asset-category-help" : undefined
                  }
                  value={f.asset_category_id}
                  onChange={(e) => {
                    const c = cats.data?.find(
                      (x: any) => x.id === Number(e.target.value),
                    );
                    if (c) setF(categoryDefaults(f, c, accounts.data ?? []));
                  }}
                >
                  <option value="">Select</option>
                  {cats.data
                    ?.filter(
                      (x: any) =>
                        x.is_active &&
                        (!registrationId ||
                          ((!x.asset_account_id ||
                            x.asset_account_id ===
                              registration.data?.asset_account_id) &&
                            groupAcceptsAccount(
                              x.fiscal_group_code,
                              accounts.data?.find(
                                (a) =>
                                  a.id === registration.data?.asset_account_id,
                              )?.account_code ?? "",
                            ))),
                    )
                    .map((x: any) => (
                      <option key={x.id} value={x.id}>
                        {x.name}
                        {x.fiscal_group_code === "LAND"
                          ? " · Tidak disusutkan"
                          : x.default_useful_life_months
                            ? ` · ${x.default_useful_life_months} bulan`
                            : ""}
                      </option>
                    ))}
                </select>
              </label>
              {selectedCategory && (
                <div
                  id="asset-category-help"
                  aria-live="polite"
                  className="mt-2 flex gap-2 rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
                >
                  <Info
                    size={15}
                    className="mt-0.5 shrink-0"
                    aria-hidden="true"
                  />
                  <div className="min-w-0 space-y-1">
                    {(selectedCategory.description ||
                      categoryNotes[selectedCategory.fiscal_group_code]) && (
                      <p className="font-medium">
                        {selectedCategory.description ||
                          categoryNotes[selectedCategory.fiscal_group_code]}
                      </p>
                    )}
                    {selectedCategory.straight_line_rate != null && (
                      <p>
                        Garis lurus {selectedCategory.straight_line_rate}% /
                        tahun
                        {selectedCategory.declining_balance_rate != null
                          ? ` · Saldo menurun ${selectedCategory.declining_balance_rate}% / tahun`
                          : ""}
                        .
                      </p>
                    )}
                    {selectedCategory.fiscal_group_code &&
                      selectedCategory.fiscal_group_code !== "LAND" && (
                        <p>
                          Sesuaikan dengan jenis aset pada ketentuan fiskal.
                        </p>
                      )}
                  </div>
                </div>
              )}
            </div>
            {f.depreciation_method !== "NONE" && (
              <div>
                <label className={field}>
                  Book Useful Life (months) *
                  <input
                    className={input}
                    type="number"
                    min={48}
                    value={f.useful_life_months}
                    onChange={(e) => set("useful_life_months", e.target.value)}
                  />
                </label>
                <p className="mt-1 text-xs text-slate-500">
                  Minimum 48 bulan. Masa manfaat pembukuan dapat berbeda dari
                  fiskal.
                </p>
              </div>
            )}
          </div>
        </section>
        <section
          className={section}
          aria-labelledby="asset-organization-heading"
        >
          <h2 id="asset-organization-heading" className={heading}>
            <MapPin size={16} className="text-emerald-700" aria-hidden="true" />
            Organization
          </h2>
          <div className={grid}>
            <label className={field}>
              Business Unit *
              <select
                required
                className={`${input}`}
                value={f.business_unit_id}
                onChange={(e) =>
                  setF({
                    ...f,
                    business_unit_id: e.target.value,
                    location_id: "",
                    department_id: "",
                  })
                }
              >
                <option value="">Select business unit</option>
                {bus.data?.map((x: any) => (
                  <option key={x.id} value={x.id}>
                    {x.code} — {x.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={field}>
              Location
              <select
                disabled={!f.business_unit_id}
                className={`${input}`}
                value={f.location_id}
                onChange={(e) =>
                  setF({ ...f, location_id: e.target.value, department_id: "" })
                }
              >
                <option value="">Optional</option>
                {loc.data?.map((x: any) => (
                  <option key={x.id} value={x.id}>
                    {x.code} — {x.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={field}>
              Department
              <select
                disabled={!f.business_unit_id}
                className={`${input}`}
                value={f.department_id}
                onChange={(e) => set("department_id", e.target.value)}
              >
                <option value="">Optional</option>
                {dep.data?.map((x: any) => (
                  <option key={x.id} value={x.id}>
                    {x.code} — {x.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
        <section className={section} aria-labelledby="asset-accounts-heading">
          <h2 id="asset-accounts-heading" className={heading}>
            <BookOpen
              size={16}
              className="text-emerald-700"
              aria-hidden="true"
            />
            Posting accounts
          </h2>
          <div className={grid}>
            <div className="min-w-0">
              <label className={field}>
                <span className="flex items-center gap-1">
                  Asset Account *
                  {Boolean(registrationId) && (
                    <LockKeyhole size={12} aria-hidden="true" />
                  )}
                </span>
                {account("asset_account_id")}
              </label>
              {Boolean(registrationId) && (
                <p className="mt-1 text-xs text-slate-500">From Item Master</p>
              )}
            </div>
            {f.depreciation_method !== "NONE" && (
              <label className={field}>
                Accumulated Depreciation *
                {account("accumulated_depreciation_account_id")}
              </label>
            )}
            {f.depreciation_method !== "NONE" && (
              <label className={field}>
                Depreciation Expense *
                {account("depreciation_expense_account_id")}
              </label>
            )}
          </div>
        </section>
        <div className="p-4 sm:px-5">
          <label className={field}>
            Notes
            <textarea
              className="min-h-16 w-full resize-y rounded-md border border-slate-300 p-2.5 text-sm text-slate-900"
              rows={2}
              value={f.notes}
              onChange={(e) => set("notes", e.target.value)}
            />
          </label>
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-4 py-3 sm:px-5">
          <WorkspaceBackButton />
          <Button
            disabled={Boolean(
              registrationId &&
              (registration.isLoading || registration.isError),
            )}
            onClick={save}
          >
            <Save size={16} aria-hidden="true" />
            Save Draft
          </Button>
        </div>
      </Card>
    </div>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Badge from "@/components/ui/Badge";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { FORM_UI } from "@/config/formUi";
import { apiErrorMessage } from "@/utils/apiError";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";

type SettingField =
  | "input_vat_account_id"
  | "accounts_payable_account_id"
  | "grni_account_id"
  | "purchase_discount_account_id"
  | "withholding_tax_payable_account_id";

type Settings = Record<SettingField, number | null> & {
  is_complete: boolean;
  missing_settings: SettingField[];
};

type Mapping = {
  field: SettingField;
  label: string;
  description: string;
  accountTypes: string[];
  normalBalance: "DEBIT" | "CREDIT";
};

const mappings: Mapping[] = [
  {
    field: "accounts_payable_account_id",
    label: "Global Accounts Payable",
    description: "Default AP control account for invoices, payments, and supplier adjustments.",
    accountTypes: ["LIABILITY"],
    normalBalance: "CREDIT",
  },
  {
    field: "grni_account_id",
    label: "Goods Received Not Invoiced (GRNI)",
    description: "Credits warehouse receipts and is cleared by receipt-backed supplier invoices.",
    accountTypes: ["LIABILITY"],
    normalBalance: "CREDIT",
  },
  {
    field: "input_vat_account_id",
    label: "Input VAT",
    description: "PPN Masukan on supplier invoices.",
    accountTypes: ["ASSET"],
    normalBalance: "DEBIT",
  },
  {
    field: "purchase_discount_account_id",
    label: "Purchase Discount",
    description: "Credit account used when a supplier invoice contains a discount.",
    accountTypes: ["INCOME", "EXPENSE"],
    normalBalance: "CREDIT",
  },
  {
    field: "withholding_tax_payable_account_id",
    label: "Withholding Tax Payable",
    description: "Liability credited for supplier-invoice withholding tax.",
    accountTypes: ["LIABILITY"],
    normalBalance: "CREDIT",
  },
];

const controlClass = `${FORM_UI.controlBase} ${FORM_UI.density[FORM_UI.defaultDensity].control} mt-1`;

export default function PostingRulesPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Partial<Record<SettingField, number | null>>>({});

  const settings = useQuery({
    queryKey: ["direct-coa-settings"],
    queryFn: async () =>
      (await api.get<Settings>("/accounting/direct-coa-settings")).data,
  });
  const accounts = useQuery({
    queryKey: ["direct-coa-settings", "posting-account-lookup"],
    queryFn: () => getAccountLookup({ is_active: true, is_posting: true }),
  });

  const selected = (field: SettingField) =>
    draft[field] ?? settings.data?.[field] ?? null;

  const save = useMutation({
    mutationFn: async () => {
      const payload = Object.fromEntries(
        mappings
          .map(({ field }) => [field, selected(field)])
          .filter(([, accountId]) => Boolean(accountId)),
      );
      if (!Object.keys(payload).length) {
        throw new Error("Choose at least one accounting control account");
      }
      return (
        await api.put<Settings>("/accounting/direct-coa-settings", payload)
      ).data;
    },
    onSuccess: async (data) => {
      setDraft({});
      queryClient.setQueryData(["direct-coa-settings"], data);
      await queryClient.invalidateQueries({ queryKey: ["direct-coa-settings"] });
      toast.success("Direct COA settings saved");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Settings could not be saved")),
  });

  const accountOptions = (mapping: Mapping) => {
    const rows = (accounts.data ?? []) as any[];
    const typed = rows.filter(
      (account) =>
        mapping.accountTypes.includes(String(account.account_type || "").toUpperCase()) &&
        String(account.normal_balance || "").toUpperCase() === mapping.normalBalance,
    );
    return typed.length ? typed : rows;
  };

  return (
    <DataWorkspace area="Finance">
      <div className="space-y-6">
        <PageHeader
          actions={<PrintPreviewButton src="/finance-setup/posting-rules/print" title="Direct COA Configuration" ariaLabel="Preview direct COA configuration" label="Print" />} title="Direct COA Setup"
          description="Global accounting controls and master-owned COA mappings for new transactions."
        />

        <ModuleSummary metrics={[
          { label: "Status", value: settings.data?.is_complete ? "Setup complete" : "Setup incomplete" },
          { label: "Configured accounts", value: `${mappings.filter(({ field }) => Boolean(selected(field))).length} of ${mappings.length}` },
          { label: "Scope", value: "Finance-wide direct COA controls" },
        ]}/>

        {settings.isLoading || accounts.isLoading
          ? <Loading message="Loading direct COA setup…" />
          : settings.isError || accounts.isError
            ? <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <p className="font-medium">Direct COA setup could not be loaded.</p>
                {settings.isError && <p>{apiErrorMessage(settings.error, "Settings could not be loaded.")}</p>}
                {accounts.isError && <p>{apiErrorMessage(accounts.error, "Posting accounts could not be loaded.")}</p>}
              </div>
            : <>
              <Card className="border-emerald-200 bg-emerald-50/40">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold text-emerald-950">
                      Direct COA transaction resolution is active
                    </h2>
                    <p className="mt-2 text-sm text-emerald-900">
                      Posting Rules are retained as read-only historical configuration.
                      New journals resolve accounts from this setup and their owning master records.
                    </p>
                  </div>
                  <Badge variant={settings.data?.is_complete ? "success" : "warning"}>
                    {settings.data?.is_complete ? "Setup complete" : "Setup incomplete"}
                  </Badge>
                </div>
                {!settings.isLoading && settings.data?.missing_settings?.length ? (
                  <p className="mt-3 text-sm text-amber-800">
                    Missing:{" "}
                    {settings.data.missing_settings
                      .map((field) => mappings.find((item) => item.field === field)?.label ?? field)
                      .join(", ")}
                  </p>
                ) : null}
              </Card>

              <div className="grid gap-4 md:grid-cols-2">
                {(accounts.data ?? []).length === 0
                  ? <div className="md:col-span-2">
                      <Empty title="No posting accounts available." description="Activate and mark chart-of-accounts records as posting before assigning control accounts." />
                    </div>
                  : <>
                    {mappings.map((mapping) => (
                      <Card key={mapping.field}>
                        <h2 className="font-semibold">{mapping.label}</h2>
                        <p className={`min-h-10 ${FORM_UI.helpText}`}>
                          {mapping.description}
                        </p>
                        <label className="mt-4 block text-sm font-medium">
                          Active posting COA
                          <select
                            className={controlClass}
                            value={selected(mapping.field) ?? ""}
                            onChange={(event) =>
                              setDraft((current) => ({
                                ...current,
                                [mapping.field]: event.target.value
                                  ? Number(event.target.value)
                                  : null,
                              }))
                            }
                          >
                            <option value="">Select account</option>
                            {accountOptions(mapping).map((account: any) => (
                              <option key={account.id} value={account.id}>
                                {account.account_code} — {account.account_name}
                              </option>
                            ))}
                          </select>
                        </label>
                      </Card>
                    ))}

                    <Card>
                      <h2 className="font-semibold">Mapping Ownership</h2>
                      <dl className="mt-3 space-y-3 text-sm">
                        <div>
                          <dt className="font-medium">Item Master</dt>
                          <dd className="text-slate-500">
                            Inventory Asset, Consumption/Expense, and COGS COA.
                          </dd>
                        </div>
                        <div>
                          <dt className="font-medium">Supplier Master</dt>
                          <dd className="text-slate-500">
                            Transitional payable fallback when Global AP is not configured.
                          </dd>
                        </div>
                        <div>
                          <dt className="font-medium">Bank/Cash Setup</dt>
                          <dd className="text-slate-500">
                            Funding COA used for payment journal credits.
                          </dd>
                        </div>
                        <div>
                          <dt className="font-medium">Journal Lines</dt>
                          <dd className="text-slate-500">
                            Account and organization-dimension snapshots for posted history.
                          </dd>
                        </div>
                      </dl>
                    </Card>
                  </>}
              </div>

              <div className="flex justify-end">
                <Button loading={save.isPending} onClick={() => save.mutate()}>
                  Save Direct COA Setup
                </Button>
              </div>
            </>}
      </div>
    </DataWorkspace>
  );
}

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { openingBalanceApi, type OpeningBalanceAccount, type OpeningBalanceLine } from "./api";

const money = (value: number) =>
  Number(value || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

type RowState = Record<number, { debit: string; credit: string }>;

function message(error: unknown) {
  const detail = (error as any)?.response?.data?.detail;
  return typeof detail === "string" ? detail : "Unable to save opening balances.";
}

export default function OpeningBalancesPage() {
  const client = useQueryClient();
  const [year, setYear] = useState(() => String(new Date().getFullYear()));
  const [rows, setRows] = useState<RowState>({});
  const [description, setDescription] = useState("");
  const fiscalYear = Number(year) || new Date().getFullYear();

  const accounts = useQuery({
    queryKey: ["opening-accounts", fiscalYear],
    queryFn: async () => (await openingBalanceApi.accounts(fiscalYear)).data,
    refetchOnWindowFocus: false,
  });
  const entries = useQuery({
    queryKey: ["opening-entries", fiscalYear],
    queryFn: async () => (await openingBalanceApi.list(fiscalYear)).data,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    const next: RowState = {};
    (accounts.data?.items ?? []).forEach((account: OpeningBalanceAccount) => {
      const debit = Number(account.existing_debit || 0);
      const credit = Number(account.existing_credit || 0);
      next[account.id] = {
        debit: debit > 0 ? String(debit) : "",
        credit: credit > 0 ? String(credit) : "",
      };
    });
    setRows(next);
  }, [accounts.data, fiscalYear]);

  const items: OpeningBalanceAccount[] = useMemo(() => accounts.data?.items ?? [], [accounts.data]);
  const totals = useMemo(() => items.reduce(
    (total, account) => ({
      debit: total.debit + (Number(rows[account.id]?.debit) || 0),
      credit: total.credit + (Number(rows[account.id]?.credit) || 0),
    }),
    { debit: 0, credit: 0 },
  ), [items, rows]);

  const saved = Number(entries.data?.count || 0) > 0;
  const canEdit = Boolean(entries.data?.can_edit);
  const loading = accounts.isLoading || entries.isLoading;
  const unavailable = accounts.isError || entries.isError;
  const save = useMutation({
    mutationFn: () => {
      const lines: OpeningBalanceLine[] = [];
      for (const account of items) {
        const debit = Number(rows[account.id]?.debit) || 0;
        const credit = Number(rows[account.id]?.credit) || 0;
        if (debit > 0) lines.push({ account_id: account.id, amount: debit, balance_type: "DEBIT" });
        if (credit > 0) lines.push({ account_id: account.id, amount: credit, balance_type: "CREDIT" });
      }
      if (saved) {
        return openingBalanceApi.revise(fiscalYear, lines, entries.data.snapshot_version, description || undefined);
      }
      return openingBalanceApi.post(fiscalYear, lines, description || undefined);
    },
    onSuccess: async () => {
      toast.success(`Opening balances saved for ${fiscalYear}.`);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["opening-accounts", fiscalYear] }),
        client.invalidateQueries({ queryKey: ["opening-entries", fiscalYear] }),
      ]);
    },
    onError: (error) => toast.error(message(error)),
  });
  const disabled = loading || unavailable || !canEdit || save.isPending;
  const canSave = saved || totals.debit > 0 || totals.credit > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Opening Balances"
        description="Set the starting debit or credit value for each balance-sheet account."
        actions={<PrintPreviewButton src={`/finance-setup/opening-balances/print?year=${fiscalYear}`} title="Opening Balance Report" ariaLabel="Preview opening balance report" label="Print" />}
      />

      <ModuleSummary metrics={[
        { label: "Fiscal Year", value: fiscalYear },
        { label: "Balance-Sheet Accounts", value: accounts.data?.count ?? 0 },
        { label: "Total Debit", value: money(totals.debit) },
        { label: "Total Credit", value: money(totals.credit) },
      ]} />

      <Card>
        <div className="mb-5 flex flex-wrap items-end gap-3">
          <label className="text-sm font-medium">
            Fiscal Year
            <Input type="number" min={2000} max={2100} className="w-40" value={year} onChange={(event) => setYear(event.target.value)} />
          </label>
          <label className="text-sm font-medium">
            Description (optional)
            <Input className="w-80" disabled={disabled} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
        </div>

        {loading ? <div className="py-12"><Loading /></div> : unavailable ? (
          <p role="alert" className="py-8 text-center text-sm text-red-600">Opening balances could not be loaded.</p>
        ) : (
          <>
            <Table variant="grid">
              <THead><TR><TH>Code</TH><TH>Name</TH><TH>Type</TH><TH>Normal</TH><TH>Debit</TH><TH>Credit</TH></TR></THead>
              <TBody>{items.map((account) => (
                <TR key={account.id}>
                  <TD className="font-mono font-medium">{account.account_code}</TD>
                  <TD>{account.account_name}</TD>
                  <TD><span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium">{account.account_type}</span></TD>
                  <TD className="text-xs text-slate-500">{account.normal_balance}</TD>
                  <TD><Input type="number" min={0} step="0.01" disabled={disabled} className="w-40 font-mono" placeholder="0.00" value={rows[account.id]?.debit ?? ""} onChange={(event) => setRows((current) => ({ ...current, [account.id]: { debit: event.target.value, credit: event.target.value ? "" : current[account.id]?.credit ?? "" } }))} /></TD>
                  <TD><Input type="number" min={0} step="0.01" disabled={disabled} className="w-40 font-mono" placeholder="0.00" value={rows[account.id]?.credit ?? ""} onChange={(event) => setRows((current) => ({ ...current, [account.id]: { credit: event.target.value, debit: event.target.value ? "" : current[account.id]?.debit ?? "" } }))} /></TD>
                </TR>
              ))}</TBody>
            </Table>
            {!items.length && <p className="py-8 text-center text-sm text-slate-500">No balance-sheet posting accounts found.</p>}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm">
                <span className="mr-4">Total Debit: <b className="font-mono">{money(totals.debit)}</b></span>
                <span>Total Credit: <b className="font-mono">{money(totals.credit)}</b></span>
              </div>
              <Button
                loading={save.isPending}
                disabled={disabled || !canSave}
                title={!canEdit ? "Open an accounting period in this fiscal year to edit opening balances." : undefined}
                onClick={() => save.mutate()}
              >
                <Save size={16} /> Save Opening Balances
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

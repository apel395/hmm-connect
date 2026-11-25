import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { FORM_UI } from "@/config/formUi";
import { apiErrorMessage } from "@/utils/apiError";

type Account = { id: number; code: string; name: string; type: string; normal_balance: string; parent_id: number | null; is_posting: boolean };
type Setup = { statistic_accounts?: Record<string,number>; effective_statistic_accounts?: Record<string,number>; statistic_options?: Record<string,{label:string;default_code:string|null;kind:string}>; profit_loss_categories?: Record<number, string>; category_options?: Record<string, string>; accounts: Account[]; settings: { report_type: string; selected_account_ids: number[] | null; header_only: boolean }[]; current_year_earnings_account_id: number | null };

const controlClass = `${FORM_UI.density[FORM_UI.defaultDensity].control} rounded border`;

export default function ReportSetupPage() {
  const [kind, setKind] = useState("PROFIT_LOSS");
  const query = useQuery({ queryKey: ["financial-report-setup"], queryFn: async () => (await api.get<Setup>("/financial-reports/setup")).data });
  const kindLabel = kind === "PROFIT_LOSS" ? "Profit & Loss" : "Balance Sheet";
  return (
    <div className="space-y-2">
      <PageHeader title="Report Setup" actions={<select aria-label="Report type" className={controlClass} value={kind} onChange={event => setKind(event.target.value)}><option value="PROFIT_LOSS">Profit & Loss</option><option value="BALANCE_SHEET">Balance Sheet</option></select>} />
      <p className={FORM_UI.helpText}>Scope: finance-wide chart-of-accounts mappings for {kindLabel}. Report setup applies to every location and department.</p>
      {query.isLoading
        ? <Loading message="Loading accounts…" />
        : query.isError
          ? <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><p>Report setup could not be loaded.</p><p>{apiErrorMessage(query.error, "Please try again.")}</p></div>
          : query.data
            ? <SetupForm key={kind} kind={kind} setup={query.data} />
            : <Empty title="Report setup is unavailable." description="No chart-of-accounts configuration was returned for this workspace." />}
    </div>
  );
}

function SetupForm({ kind, setup }: { kind: string; setup: Setup }) {
  const saved = setup.settings.find(value => value.report_type === kind);
  const [selected, setSelected] = useState<number[] | null>(saved?.selected_account_ids ?? null);
  const [headerOnly, setHeaderOnly] = useState(saved?.header_only ?? false);
  const [earnings, setEarnings] = useState(String(setup.current_year_earnings_account_id ?? ""));
  const [categories, setCategories] = useState<Record<number, string>>(setup.profit_loss_categories ?? {});
  const [statisticAccounts, setStatisticAccounts] = useState<Record<string,number>>(setup.statistic_accounts ?? {});
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();
  const accounts = useMemo(() => setup.accounts.filter(a => (kind === "PROFIT_LOSS" ? ["REVENUE", "INCOME", "EXPENSE"] : ["ASSET", "LIABILITY", "EQUITY"]).includes(a.type)), [kind, setup.accounts]);
  const ids = selected ?? accounts.filter(a => a.is_posting).map(a => a.id);
  const descendants = (account: Account) => {
    if (["REVENUE", "INCOME"].includes(account.type)) return accounts.filter(a => ["REVENUE", "INCOME"].includes(a.type) && a.is_posting).map(a => a.id);
    const found: number[] = [];
    const visit = (current: Account, seen = new Set<number>()) => {
      if (seen.has(current.id)) return;
      seen.add(current.id);
      if (current.is_posting) found.push(current.id);
      accounts.filter(a => a.parent_id === current.id).forEach(child => visit(child, seen));
    };
    visit(account);
    return found;
  };
  const save = useMutation({ mutationFn: async () => api.put(`/financial-reports/setup/${kind}`, { statistic_accounts: kind === "PROFIT_LOSS" ? statisticAccounts : undefined, profit_loss_categories: kind === "PROFIT_LOSS" ? categories : undefined, selected_account_ids: selected, header_only: headerOnly, current_year_earnings_account_id: Number(earnings) || null }),
    onSuccess: () => { toast.success("Report setup saved"); queryClient.invalidateQueries({ queryKey: ["financial-report-setup"] }); queryClient.invalidateQueries({ queryKey: ["financial-report-comparison"] }); },
    onError: (error: unknown) => toast.error(apiErrorMessage(error, "Report setup could not be saved")) });
  const shown = accounts.filter(account => `${account.code} ${account.name}`.toLowerCase().includes(search.toLowerCase()));
  return <form className="space-y-2" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <div className="flex flex-wrap items-center gap-2 text-xs"><input aria-label="Search report accounts" className={controlClass} placeholder="Search accounts" value={search} onChange={event => setSearch(event.target.value)} />
      <Button size="sm" variant="outline" type="button" onClick={() => setSelected(null)}>Select all</Button><Button size="sm" variant="outline" type="button" onClick={() => setSelected([])}>Clear</Button>
      <label className="flex items-center gap-1"><input type="checkbox" checked={headerOnly} onChange={event => setHeaderOnly(event.target.checked)} />KAP: account headers only</label>
      <label>Current-year earnings <select aria-label="Current-year earnings account" className={controlClass} value={earnings} onChange={event => setEarnings(event.target.value)}><option value="">Select account</option>{setup.accounts.filter(a => a.type === "EQUITY" && a.normal_balance === "CREDIT" && a.is_posting).map(a => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></label>
      <Button size="sm" type="submit" disabled={save.isPending}>Save</Button>
    </div>
    {kind === "PROFIT_LOSS" && <details className="rounded border bg-white p-2 text-xs"><summary className="cursor-pointer font-medium">Statistics and ADR sources</summary><div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(setup.statistic_options ?? {}).map(([key,option])=>{
      const effective=setup.accounts.find(a=>a.id===setup.effective_statistic_accounts?.[key]);
      const choices=setup.accounts.filter(a=>option.kind === "financial" ? ["REVENUE","INCOME"].includes(a.type) : a.type === "STATISTIC" && a.code !== "900" && !setup.accounts.some(child=>child.parent_id===a.id));
      return <label key={key} className="grid gap-1">{option.label}<select aria-label={`${option.label} source`} className={`${controlClass} min-w-0`} value={statisticAccounts[key]??""} onChange={event=>{const next={...statisticAccounts};if(event.target.value)next[key]=Number(event.target.value);else delete next[key];setStatisticAccounts(next);}}><option value="">{option.default_code?`Automatic: ${option.default_code}${effective?` ${effective.name}`:""}`:"Not configured"}</option>{choices.map(a=><option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></label>;
    })}</div><p className="mt-2 text-slate-500">Enter quantities in Statistics for the selected month and location. Use room-nights for room counts. Select paid room nights sold for ADR; use Room Occupied only when it excludes complimentary rooms. Bookkeeping Rate uses the latest recorded rate and its currency-pair unit.</p></details>}
    {shown.length === 0
      ? <Empty title="No accounts match this scope." description="Clear the search or choose another report type to see accounts." />
      : <div className="max-h-[70vh] overflow-auto rounded border"><table className="w-full whitespace-nowrap text-xs"><thead className="sticky top-0 bg-slate-100"><tr><th className="w-10 p-1.5">Show</th><th className="p-1.5 text-left">Account</th><th className="p-1.5 text-left">Name</th><th className="p-1.5 text-left">Type</th>{kind === "PROFIT_LOSS" && <th className="p-1.5 text-left">Report category</th>}</tr></thead><tbody>{shown.map(account => {
        const children = descendants(account);
        const checked = children.length > 0 && children.every(id => ids.includes(id));
        return <tr key={account.id} className={`border-b ${!account.is_posting ? "bg-slate-50 font-semibold" : ""}`}><td className="p-1 text-center"><input aria-label={`Show ${account.code} ${account.name}`} type="checkbox" disabled={!children.length} checked={checked} onChange={event => setSelected(event.target.checked ? [...new Set([...ids, ...children])] : ids.filter(id => !children.includes(id)))} /></td><td className="p-1">{account.code}</td><td className="p-1">{account.name}</td><td className="p-1">{account.type}</td>{kind === "PROFIT_LOSS" && <td className="p-1">{account.is_posting && account.type === "EXPENSE" ? <select aria-label={`Report category for ${account.name}`} className={controlClass} value={categories[account.id] ?? ""} onChange={event => { const next = { ...categories }; if (event.target.value) next[account.id] = event.target.value; else delete next[account.id]; setCategories(next); }}><option value="">Existing COA classification</option>{Object.entries(setup.category_options ?? {}).filter(([key]) => !["REVENUE", "NONOPERATING_INCOME"].includes(key)).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select> : "—"}</td>}</tr>;
      })}</tbody></table></div>}
  </form>;
}

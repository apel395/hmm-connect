import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import DataWorkspace, { WorkspaceFilters } from "@/components/workspace/DataWorkspace";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import SearchableSelect from "@/components/form/SearchableSelect";
import { FORM_UI } from "@/config/formUi";
import useAuthStore from "@/store/auth";
import { posErrorMessage } from "../errors";
import { usePosOperations, usePosOptions, usePosOutletReport } from "../hooks/usePosData";
import { hotelOutletContext } from "../outletContext";
import { operationsApi, type Shift } from "../operationsApi";

const input = `${FORM_UI.controlBase} ${FORM_UI.density.compact.control}`;
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jakarta" }).format(new Date());
const money = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { style: "currency", currency: "IDR" });
const tabs = ["Orders", "Tables", "Shifts", "Reports"] as const;
type OperationsTab = (typeof tabs)[number];

export default function PosOperationsPage() {
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const manage = useAuthStore((state) => state.hasPermission("finance.manage"));
  const admin = useAuthStore((state) => state.hasPermission("admin.settings.manage"));
  const sell = useAuthStore((state) => state.hasPermission("pos.sell"));
  const [location, setLocation] = useState<number | undefined>(Number(params.get("location")) || undefined);
  const [department, setDepartment] = useState<number | undefined>(Number(params.get("outlet")) || undefined);
  const [tab, setTab] = useState<OperationsTab>("Orders");
  const [error, setError] = useState("");
  const [opening, setOpening] = useState("");
  const [closing, setClosing] = useState<Shift | null>(null);
  const [counted, setCounted] = useState("");
  const [reason, setReason] = useState("");
  const [from, setFrom] = useState(today());
  const [to, setTo] = useState(today());
  const [cashier, setCashier] = useState("");

  const options = usePosOptions(user?.id);
  const selection = hotelOutletContext(options.data, location, department);
  const { locations, departments } = selection;
  const scope = { location_id: selection.location?.id ?? 0, department_id: selection.department?.id ?? 0 };
  const context = usePosOperations(user?.id, scope, selection.valid);
  const report = usePosOutletReport(
    user?.id,
    scope,
    { from, to, cashier: cashier ? Number(cashier) : undefined },
    Boolean(selection.valid && tab === "Reports" && from && to && to >= from),
  );

  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["pos-options"] });
    void client.invalidateQueries({ queryKey: ["pos-operations"] });
    void client.invalidateQueries({ queryKey: ["pos-outlet-report"] });
  };
  const action = useMutation({
    mutationFn: async (fn: () => Promise<unknown>) => {
      await fn();
    },
    onSuccess: () => {
      setError("");
      setClosing(null);
      setCounted("");
      setReason("");
      setOpening("");
      refresh();
    },
    onError: (cause: unknown) => setError(posErrorMessage(cause)),
  });
  const run = (fn: () => Promise<unknown>) => {
    setError("");
    action.mutate(fn);
  };

  const resetShiftForms = () => {
    setClosing(null);
    setOpening("");
    setCounted("");
    setReason("");
  };
  const changeLocation = (value?: number) => {
    setLocation(value);
    setDepartment(undefined);
    setParams(value ? { location: String(value) } : {}, { replace: true });
    setCashier("");
    setError("");
    resetShiftForms();
  };
  const changeOutlet = (value?: number) => {
    setDepartment(value);
    setParams({
      ...(selection.location ? { location: String(selection.location.id) } : {}),
      ...(value ? { outlet: String(value) } : {}),
    }, { replace: true });
    setCashier("");
    setError("");
    resetShiftForms();
  };
  const newOrder = `/pos?location=${location}&outlet=${department}`;
  const cashierChoices = Array.from(
    new Map(
      (context.data?.shifts ?? []).map((shift) => [
        shift.cashier_id,
        { id: shift.cashier_id, name: shift.cashier_name || `Cashier ${shift.cashier_id}` },
      ]),
    ).values(),
  );

  return (
    <DataWorkspace area="Reports">
      <div className="space-y-3">
        <PageHeader
          title="Hotel POS · Food & Beverage"
          description="Outlet orders, tables, cashier shifts and posted sales."
          actions={<Button variant="outline" size="sm" onClick={() => window.print()}><Printer size={15} />Print</Button>}
        />
        <WorkspaceFilters label="Outlet filters" context={selection.location && selection.department ? `${selection.location.name} · ${selection.department.name}` : "Choose an outlet"}>
          <div className="grid gap-2 sm:grid-cols-2">
            <SearchableSelect
              label="Hotel location"
              value={selection.location?.id}
              options={locations}
              onChange={changeLocation}
            />
            <SearchableSelect
              label="Outlet"
              value={selection.department?.id}
              options={departments.map((row) => ({ ...row, name: row.code ? `${row.code} · ${row.name}` : row.name }))}
              onChange={changeOutlet}
            />
          </div>
        </WorkspaceFilters>
        {(admin || manage) && (
          <Link className="inline-block text-sm text-emerald-700 underline" to={`/settings/pos${selection.location ? `?location=${selection.location.id}${selection.department ? `&outlet=${selection.department.id}` : ""}` : ""}`}>
            POS Settings
          </Link>
        )}
        <div className="hidden print:block text-sm">
          {locations.find((row) => row.id === location)?.name} · {departments.find((row) => row.id === department)?.name}
        </div>
        {options.isError && (
          <p role="alert" className="text-sm text-red-700">
            Hotel locations could not load. <button type="button" className="underline" onClick={() => void options.refetch()}>Retry</button>
          </p>
        )}
        {selection.invalidLink && (
          <p role="status" className="text-sm text-slate-600">This link does not identify an accessible Hotel outlet. Choose an accessible Hotel location and outlet.</p>
        )}

        {selection.valid ? (
          <>
            <nav className="flex gap-1 border-b print:hidden" aria-label="Outlet sections">
              {tabs.map((name) => (
                <button
                  key={name}
                  type="button"
                  className={`px-3 py-2 text-sm ${tab === name ? "border-b-2 border-emerald-700 font-semibold text-emerald-800" : "text-slate-600"}`}
                  onClick={() => setTab(name)}
                >
                  {name}
                </button>
              ))}
            </nav>
            {(context.isError || report.isError) && (
              <p role="alert" className="text-sm text-red-700">
                Outlet data could not load. {posErrorMessage(context.isError ? context.error : report.error)}
              </p>
            )}
            {error && <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
            {context.isLoading ? (
              <Loading message="Loading outlet…" />
            ) : context.isError ? null : context.data && !context.data.order_mode ? (
              <p className="text-sm">Configure TABLE, COUNTER or EVENT in POS Settings before opening a cashier shift.</p>
            ) : context.data ? (
              <p className="text-xs text-slate-500 print:hidden">{context.data.order_mode} orders · tables and shifts belong to this outlet</p>
            ) : null}

            {tab === "Orders" && (
              <>
                <div className="flex justify-end print:hidden">
                  {sell && context.data?.order_mode && <Link className="rounded bg-emerald-700 px-3 py-2 text-sm text-white" to={newOrder}>Open order</Link>}
                </div>
                {context.data?.orders.length === 0 ? (
                  <Empty title="No open orders" description="Orders created in this outlet appear here until they are settled." />
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead><tr><th>Order</th><th>Table / event</th><th>Guests</th><th>Cashier</th><th className="text-right">Total</th><th /></tr></thead>
                    <tbody>
                      {(context.data?.orders ?? []).map((order) => (
                        <tr key={order.id} className="border-t">
                          <td className="py-2">{order.number}</td>
                          <td>{order.table || order.event || "Counter"}</td>
                          <td>{order.guest_count ?? "—"}</td>
                          <td>{order.cashier_id}</td>
                          <td className="text-right">{money(order.total)}</td>
                          <td className="text-right">
                            {sell && order.cashier_id === user?.id && <Link className="text-emerald-700 underline" to={`/pos?order=${order.id}`}>Continue / settle</Link>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}

            {tab === "Tables" && (
              context.data?.tables.length === 0 ? (
                <Empty title="No tables configured" description="Add tables in POS Settings when this outlet uses table orders." />
              ) : (
                <div className="grid gap-2 md:grid-cols-4">
                  {(context.data?.tables ?? []).map((table) => (
                    <div key={table.id} className="rounded border bg-white p-3">
                      <strong>{table.name}</strong>
                      <div className="text-xs">
                        {table.seats} seats · {!table.is_active
                          ? <Badge variant="secondary">INACTIVE</Badge>
                          : <Badge variant={table.status === "AVAILABLE" ? "success" : "warning"}>{table.status}</Badge>}
                      </div>
                      {table.order_id && <Link className="text-xs text-emerald-700 underline" to={`/pos?order=${table.order_id}`}>Continue order</Link>}
                    </div>
                  ))}
                </div>
              )
            )}

            {tab === "Shifts" && (
              <>
                <div className="flex gap-2 print:hidden">
                  {sell && !context.data?.shifts.some((shift) => shift.cashier_id === user?.id && shift.status === "OPEN") && (
                    <>
                      <input aria-label="Opening cash" className={input} placeholder="Opening cash" type="number" min={0} step="0.01" value={opening} onChange={(event) => setOpening(event.target.value)} />
                      <Button
                        disabled={!context.data?.order_mode || opening === "" || Number(opening) < 0 || action.isPending}
                        onClick={() => run(() => operationsApi.openShift(scope, opening))}
                      >
                        Open my shift
                      </Button>
                    </>
                  )}
                </div>
                {context.data?.shifts.length === 0 ? (
                  <Empty title="No cashier shifts" description="Open a shift before taking outlet orders." />
                ) : (
                  (context.data?.shifts ?? []).map((shift) => (
                    <section key={shift.id} className="mt-3 rounded border bg-white p-3 text-sm">
                      <div className="flex flex-wrap justify-between gap-2">
                        <strong>Shift #{shift.id} · {shift.cashier_name} · <Badge variant={shift.status === "OPEN" ? "success" : "secondary"}>{shift.status}</Badge></strong>
                        <span>{shift.opened_at} {shift.closed_at ? `→ ${shift.closed_at}` : ""}</span>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 lg:grid-cols-4">
                        <span>Opening {money(shift.opening_cash)}</span>
                        <span>Cash sales {money(shift.payments.CASH)}</span>
                        <span>Expected {money(shift.expected_cash)}</span>
                        <span>Counted {shift.counted_cash === null ? "—" : money(shift.counted_cash)}</span>
                        <span>Card {money(shift.payments.CARD)}</span>
                        <span>Bank {money(shift.payments.BANK_TRANSFER)}</span>
                        <span>PBJT {money(shift.pbjt)}</span>
                        <span>Service {money(shift.service_charge)}</span>
                        <span>Difference {shift.cash_difference === null ? "—" : money(shift.cash_difference)}</span>
                        <span>Open orders {shift.open_orders}</span>
                      </div>
                      {sell && shift.status === "OPEN" && (shift.cashier_id === user?.id || manage) && (
                        <Button className="mt-2 print:hidden" size="sm" variant="outline" disabled={shift.open_orders > 0} onClick={() => { setClosing(shift); setCounted(""); setReason(""); }}>
                          Close shift
                        </Button>
                      )}
                      <Link className="mt-2 inline-block text-xs text-emerald-700 underline print:hidden" target="_blank" to={`/pos/operations/shifts/${shift.id}/print`}>Print shift report</Link>
                      {shift.transactions.length > 0 && (
                        <details className="mt-2">
                          <summary>Shift transactions</summary>
                          {shift.transactions.map((transaction) => (
                            <div key={transaction.id} className="flex justify-between border-t py-1">
                              <span>{transaction.number} · {transaction.method}</span>
                              <span>{money(transaction.total)}</span>
                            </div>
                          ))}
                        </details>
                      )}
                    </section>
                  ))
                )}
                {closing && (
                  <section className="mt-3 space-y-2 rounded border border-emerald-300 bg-white p-3 print:hidden">
                    <strong>Close shift #{closing.id}</strong>
                    <div>Expected cash {money(closing.expected_cash)}</div>
                    <input aria-label="Counted cash" className={input} type="number" min={0} step="0.01" placeholder="Counted cash" value={counted} onChange={(event) => setCounted(event.target.value)} />
                    <input aria-label="Cash difference reason" className={`${input} w-full`} placeholder="Reason for any difference" value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} />
                    <div className="flex gap-2">
                      <Button disabled={counted === "" || Number(counted) < 0 || action.isPending} onClick={() => run(() => operationsApi.closeShift(closing.id, counted, reason))}>Confirm close</Button>
                      <Button variant="ghost" onClick={() => setClosing(null)}>Cancel</Button>
                    </div>
                  </section>
                )}
              </>
            )}

            {tab === "Reports" && (
              <>
                <WorkspaceFilters label="Report filters" context={`${from} → ${to}`}>
                  <div className="flex flex-wrap gap-2">
                    <input aria-label="From date" type="date" className={input} value={from} onChange={(event) => setFrom(event.target.value)} />
                    <input aria-label="To date" type="date" className={input} value={to} onChange={(event) => setTo(event.target.value)} />
                    <SearchableSelect<number>
                      label="Report cashier"
                      value={cashier ? Number(cashier) : undefined}
                      options={cashierChoices}
                      placeholder="All cashiers"
                      onChange={(value) => setCashier(value ? String(value) : "")}
                    />
                  </div>
                </WorkspaceFilters>
                {to < from && <p className="text-red-700">Choose a valid date range.</p>}
                <h2 className="my-2 font-semibold">Outlet sales · {from} to {to}</h2>
                {report.isLoading ? (
                  <Loading message="Loading outlet report…" />
                ) : report.data ? (
                  <>
                    <ModuleSummary metrics={[
                      { label: "Sales", value: report.data.sales },
                      { label: "Gross", value: money(report.data.gross) },
                      { label: "Cash", value: money(report.data.payments.CASH) },
                      { label: "Card", value: money(report.data.payments.CARD) },
                      { label: "Bank", value: money(report.data.payments.BANK_TRANSFER) },
                      { label: "Service charge", value: money(report.data.service_charge) },
                      { label: "PBJT", value: money(report.data.pbjt) },
                      { label: "Other tax", value: money(report.data.other_tax) },
                    ]} />
                    {report.data.daily.length === 0 ? (
                      <Empty title="No posted sales" description="No posted POS sales match this date range and cashier." />
                    ) : (
                      <table className="mt-3 w-full text-left text-sm">
                        <thead><tr><th>Date</th><th>Sales</th><th>Cash</th><th>Card</th><th>Bank</th><th>PBJT</th><th>Service</th><th>Total</th></tr></thead>
                        <tbody>
                          {report.data.daily.map((day) => (
                            <tr key={day.date} className="border-t">
                              <td className="py-2">{day.date}</td>
                              <td>{day.sales}</td>
                              <td>{money(day.payments.CASH)}</td>
                              <td>{money(day.payments.CARD)}</td>
                              <td>{money(day.payments.BANK_TRANSFER)}</td>
                              <td>{money(day.pbjt)}</td>
                              <td>{money(day.service_charge)}</td>
                              <td>{money(day.gross)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    <h3 className="mt-3 font-semibold">Sales by cashier</h3>
                    {report.data.cashiers.length === 0 ? (
                      <p className="py-2 text-sm text-slate-500">No cashier totals for this period.</p>
                    ) : (
                      report.data.cashiers.map((cashierRow) => (
                        <div key={cashierRow.cashier_id} className="flex justify-between border-t py-1 text-sm">
                          <span>{cashierRow.name} · {cashierRow.sales} sales</span>
                          <span>{money(cashierRow.gross)}</span>
                        </div>
                      ))
                    )}
                  </>
                ) : null}
              </>
            )}
          </>
        ) : options.isLoading ? (
          <Loading message="Loading Hotel locations…" />
        ) : options.isError ? null : locations.length === 0 ? (
          <p className="text-sm text-slate-500">No Hotel locations are available for this account. <Link className="text-emerald-700 underline" to="/pos">Open the Register for Catering sales</Link></p>
        ) : selection.location && departments.length === 0 ? (
          <p className="text-sm text-slate-500">No Food &amp; Beverage outlets are configured for this Hotel location. {admin ? "Open POS Settings to create a Restaurant, Coffee Shop or another outlet." : "Ask an administrator to configure its F&B outlets."}</p>
        ) : (
          <p className="text-sm text-slate-500">Choose a Hotel location and outlet.</p>
        )}
      </div>
    </DataWorkspace>
  );
}

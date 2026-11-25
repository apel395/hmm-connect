import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {KeyRound, LogOut, Printer, RefreshCw, Users} from "lucide-react";
import { toast } from "sonner";
import ModuleSummary from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import useAuthStore from "@/store/auth";
import { apiErrorMessage } from "@/utils/apiError";
import { userApi } from "../users/userApi";
import { useActiveSessions, userKeys } from "../users/useUsers";

function formatRelative(iso: string | null, idleSeconds: number | null): string {
  if (!iso) return "—";
  const now = Date.now();
  const then = new Date(iso).getTime();
  const seconds = idleSeconds ?? Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function formatIdle(idleSeconds: number | null): string {
  if (idleSeconds === null) return "—";
  if (idleSeconds < 60) return `${idleSeconds}s`;
  if (idleSeconds < 3600) return `${Math.floor(idleSeconds / 60)}m`;
  if (idleSeconds < 86400) return `${Math.floor(idleSeconds / 3600)}h ${Math.floor((idleSeconds % 3600) / 60)}m`;
  return `${Math.floor(idleSeconds / 86400)}d`;
}

export default function ActiveSessionsPage() {
  const qc = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const [clearing, setClearing] = useState<number | null>(null);
  const sessions = useActiveSessions();

  async function clear(sessionId: number, username: string) {
    const fullName = sessions.data?.items.find((item) => item.id === sessionId)?.full_name ?? username;
    if (!window.confirm(`Sign out ${fullName} (${username})? Their active session will be invalidated immediately.`)) return;
    setClearing(sessionId);
    try {
      await userApi.clearSession(sessionId);
      await qc.invalidateQueries({ queryKey: userKeys.sessions() });
      toast.success(`Session cleared for ${username}.`);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Session could not be cleared.");
    } finally {
      setClearing(null);
    }
  }

  async function refresh() {
    await qc.invalidateQueries({ queryKey: userKeys.sessions() });
  }

  const items = sessions.data?.items ?? [];

  return (
    <DataWorkspace area="Admin">
      <PageHeader title="Active Sessions" description="View signed-in users and force sign-out any user whose session is stuck or no longer needed." actions={<>
        <Button variant="outline" onClick={refresh} loading={sessions.isFetching}><RefreshCw size={16}/> Refresh</Button>
        <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
      </>}/>
      <ModuleSummary metrics={[
        { label: "Active sessions", value: sessions.data?.total_active_sessions ?? items.length },
        { label: "Shown", value: items.length, note: "On this page" },
        { label: "Idle", value: items.filter((item) => item.is_idle).length, note: "On this page" },
        { label: "Active now", value: items.filter((item) => !item.is_idle).length, note: "On this page" },
      ]}/>
      {sessions.isError && <div role="alert" className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">Active sessions could not be loaded. {apiErrorMessage(sessions.error, "Retry the failed request.")}</div>}
      <Card>
        {sessions.isLoading ? <div className="py-12"><Loading message="Loading active sessions..."/></div>
          : sessions.isError ? null
          : items.length === 0 ? <Empty icon={<Users className="h-8 w-8"/>} title="No active sessions." description="Signed-in users appear here while their sessions are valid."/>
          : <>
            <div className={sessions.isFetching ? "opacity-70" : ""}>
              <Table className="min-w-[820px]" containerClassName="border-0 shadow-none">
                <THead><TR className="whitespace-nowrap"><TH>User</TH><TH>Organization</TH><TH>Roles</TH><TH>Last Activity</TH><TH>Idle</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead>
                <TBody>{items.map((session) => {
                  const isSelf = session.id === (currentUser as any)?.id;
                  return <TR key={session.id}>
                    <TD className="max-w-[260px]"><TableCellStack primary={session.full_name} secondary={`${session.username} · ${session.email}`}/></TD>
                    <TD>{session.department?.name || session.location?.name ? <TableCellStack primary={session.department?.name || session.location?.name} secondary={session.department?.name ? session.location?.name : undefined}/> : "—"}</TD>
                    <TD><div className="flex max-w-sm flex-wrap gap-1">{session.roles.length ? session.roles.map((role) => <Badge key={role.id} variant="outline">{role.name}</Badge>) : <span className="text-sm text-slate-400">—</span>}</div></TD>
                    <TD className="whitespace-nowrap">{formatRelative(session.session_last_activity_at, session.idle_seconds)}</TD>
                    <TD className="whitespace-nowrap">{formatIdle(session.idle_seconds)}</TD>
                    <TD>{session.is_idle ? <Badge variant="warning"><KeyRound size={11} className="mr-1"/> Idle</Badge> : <Badge variant="success">Active</Badge>}</TD>
                    <TD><div className="flex justify-end gap-2"><Button size="sm" variant={isSelf ? "outline" : "danger"} disabled={isSelf || clearing === session.id} loading={clearing === session.id} onClick={() => clear(session.id, session.username)}><LogOut size={14}/> {isSelf ? "Current" : "Sign Out"}</Button></div></TD>
                  </TR>;
                })}</TBody>
              </Table>
            </div>
            <p className="mt-4 text-sm text-slate-500">Showing <span className="font-semibold">{items.length}</span> active session{ items.length === 1 ? "" : "es" }. Sessions idle longer than 30 minutes are expired automatically on their next request.</p>
          </>}
      </Card>
    </DataWorkspace>
  );
}

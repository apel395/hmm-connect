import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {KeyRound, Pencil, Plus, Search, Trash2, Printer} from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Label from "@/components/ui/Label";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { roleApi, type ManagedRole } from "./roleApi";

const PAGE_SIZE = 20;
const CORE_ROLES = new Set(["SYSTEM_ADMINISTRATOR", "GENERAL_MANAGER", "PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT", "AUDITOR", "VIEWER"]);

function errorMessage(error: any, fallback: string) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  return fallback;
}

export default function RolePage() {
  const qc = useQueryClient();
  const roles = useQuery({ queryKey: ["managed-roles"], queryFn: roleApi.list });
  const permissions = useQuery({ queryKey: ["managed-permissions"], queryFn: roleApi.permissions });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<ManagedRole | null | "new">(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [permissionCodes, setPermissionCodes] = useState<string[]>([]);

  const editingRole = editing && editing !== "new" ? editing : null;
  const editingCoreRole = Boolean(editingRole && CORE_ROLES.has(editingRole.name));

  const save = useMutation({
    mutationFn: async () => {
      const payload = { name: name.trim(), description: description.trim() || null, permission_codes: [...new Set(permissionCodes)] };
      return editing === "new" ? roleApi.create(payload) : roleApi.update((editing as ManagedRole).id, payload);
    },
    onSuccess: async () => {
      toast.success("Role saved.");
      setEditing(null);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["managed-roles"] }),
        qc.invalidateQueries({ queryKey: ["managed-permissions"] }),
      ]);
    },
    onError: (error: any) => toast.error(errorMessage(error, "Role could not be saved.")),
  });
  const remove = useMutation({
    mutationFn: roleApi.remove,
    onSuccess: () => { toast.success("Role deleted."); qc.invalidateQueries({ queryKey: ["managed-roles"] }); },
    onError: (error: any) => toast.error(errorMessage(error, "Role could not be deleted.")),
  });

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (roles.data ?? []).filter((role) => [role.name, role.description, ...role.permissions.map((item) => item.code)].filter(Boolean).join(" ").toLowerCase().includes(term));
  }, [roles.data, search]);
  const pages = Math.max(Math.ceil(filtered.length / PAGE_SIZE), 1);
  const visibleRoles = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  useEffect(() => { setPage(1); }, [search]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  function openRole(role?: ManagedRole) {
    if (role) {
      setEditing(role);
      setName(role.name);
      setDescription(role.description || "");
      setPermissionCodes([...new Set(role.permissions.map((item) => item.code))]);
    } else {
      setEditing("new");
      setName("");
      setDescription("");
      setPermissionCodes([]);
    }
  }

  function togglePermission(code: string, checked: boolean) {
    setPermissionCodes((current) => {
      const next = new Set(current);
      if (checked) next.add(code); else next.delete(code);
      return [...next];
    });
  }

  return <div className="space-y-6">
    <PageHeader title="Roles" description="Manage core HMM-Connect roles and additional custom roles." actions={<>
<Button onClick={() => openRole()}><Plus size={16}/> Create Role</Button>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}/>
    <Card>
      <div className="mb-5 relative max-w-md"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400"/><Input value={search} onChange={(event)=>setSearch(event.target.value)} className="pl-9" placeholder="Search roles or permissions..."/></div>
      {roles.isLoading ? <div className="py-12"><Loading/></div> : roles.isError ? <p className="py-10 text-center text-sm text-red-600">Roles could not be loaded.</p> : filtered.length===0 ? <div className="py-12 text-center"><KeyRound className="mx-auto mb-2 h-8 w-8 text-slate-400"/><p className="text-sm text-slate-500">No roles found.</p></div> : <><Table className="min-w-[760px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Role</TH><TH numeric>Users</TH><TH>Permissions</TH><TH numeric>Actions</TH></TR></THead><TBody>{visibleRoles.map((role)=><TR key={role.id}><TD className="max-w-[280px]"><TableCellStack primary={role.name} secondary={role.description || undefined}/></TD><TD numeric className="font-semibold">{role.user_count}</TD><TD><div className="flex max-w-xl flex-wrap gap-1">{role.permissions.map((p)=><Badge key={p.code} variant="outline">{p.code}</Badge>)}</div></TD><TD><div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={()=>openRole(role)}><Pencil size={14}/> Edit</Button><Button size="sm" variant="danger" disabled={CORE_ROLES.has(role.name) || role.user_count>0} onClick={()=>{if(window.confirm(`Delete role ${role.name}?`)) remove.mutate(role.id)}}><Trash2 size={14}/> Delete</Button></div></TD></TR>)}</TBody></Table><Pagination page={page} pages={pages} total={filtered.length} pageSize={PAGE_SIZE} noun="roles" onChange={setPage}/></>}
    </Card>
    <Dialog open={editing!==null} onOpenChange={(open)=>!open&&setEditing(null)}><DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto"><DialogHeader><DialogTitle>{editing==="new"?"Create Role":"Edit Role"}</DialogTitle></DialogHeader><DialogBody className="space-y-5"><div><Label required>Role Name</Label><Input disabled={editingCoreRole} value={name} onChange={(e)=>setName(e.target.value)} placeholder="e.g. PURCHASING"/>{editingCoreRole&&<p className="mt-1 text-xs text-slate-500">Core role names are fixed because application authorization refers to these canonical names.</p>}</div><div><Label>Description</Label><Input value={description} onChange={(e)=>setDescription(e.target.value)}/></div><div><Label>Permissions</Label>{permissions.isLoading?<div className="mt-4"><Loading/></div>:permissions.isError?<p className="mt-2 text-sm text-red-600">Permissions could not be loaded.</p>:<div className="mt-2 grid gap-2 sm:grid-cols-2">{(permissions.data ?? []).map((permission)=><label key={permission.code} className="flex items-start gap-2 rounded border p-3 text-sm"><input type="checkbox" className="mt-1" checked={permissionCodes.includes(permission.code)} onChange={(event)=>togglePermission(permission.code,event.target.checked)}/><span><span className="font-medium">{permission.code}</span>{permission.description&&<span className="block text-xs text-slate-500">{permission.description}</span>}</span></label>)}</div>}</div></DialogBody><DialogFooter><Button variant="outline" onClick={()=>setEditing(null)}>Cancel</Button><Button loading={save.isPending} disabled={!name.trim() || permissions.isLoading} onClick={()=>save.mutate()}>Save Role</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}

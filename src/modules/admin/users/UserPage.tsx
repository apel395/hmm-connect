import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2, Users } from "lucide-react";
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
import useAuthStore from "@/store/auth";
import { userApi } from "./userApi";
import { useAssignableDepartments, useAssignableLocations, useAssignableRoles, useUserDetail, useUsers, userKeys } from "./useUsers";

const PAGE_SIZE = 25;

export default function UserPage() {
  const qc = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const users = useUsers({ page, page_size: PAGE_SIZE, search: debouncedSearch || undefined });
  const [editor, setEditor] = useState<number | "new" | null>(null);
  const detail = useUserDetail(typeof editor === "number" ? editor : null);
  const roles = useAssignableRoles(editor !== null);
  const departments = useAssignableDepartments(editor !== null);
  const locations = useAssignableLocations(editor !== null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [departmentId, setDepartmentId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (editor === "new") { setUsername(""); setEmail(""); setFullName(""); setPassword(""); setIsActive(true); setDepartmentId(""); setLocationId(""); setRoleIds([]); return; }
    if (!detail.data) return;
    setUsername(detail.data.username); setEmail(detail.data.email); setFullName(detail.data.full_name); setPassword(""); setIsActive(detail.data.is_active); setDepartmentId(detail.data.department_id ? String(detail.data.department_id) : ""); setLocationId(detail.data.location_id ? String(detail.data.location_id) : ""); setRoleIds(detail.data.role_ids);
  }, [detail.data, editor]);

  const visibleUsers = users.data?.items ?? [];
  const selectableIds = visibleUsers.filter((user) => user.id !== (currentUser as any)?.id).map((user) => user.id);
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  const total = users.data?.total_items ?? 0;
  const pages = Math.max(users.data?.total_pages ?? 0, 1);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  async function save() {
    if (!username.trim() || !email.trim() || !fullName.trim()) return toast.error("Username, email and full name are required.");
    if (editor === "new" && password.length < 8) return toast.error("Password must be at least 8 characters.");
    if (editor !== "new" && password && password.length < 8) return toast.error("New password must be at least 8 characters.");
    setSaving(true);
    try {
      if (editor === "new") await userApi.create({ username:username.trim(), email:email.trim(), full_name:fullName.trim(), password, is_active:isActive, department_id:departmentId?Number(departmentId):null, location_id:locationId?Number(locationId):null, role_ids:roleIds });
      else if (typeof editor === "number") { await userApi.update(editor,{ username:username.trim(), email:email.trim(), full_name:fullName.trim(), ...(password ? { password } : {}), is_active:isActive, department_id:departmentId?Number(departmentId):null, location_id:locationId?Number(locationId):null }); await userApi.replaceRoles(editor,roleIds); }
      await qc.invalidateQueries({queryKey:userKeys.all}); toast.success(editor==="new"?"User created.":"User updated."); setEditor(null);
    } catch (error:any) { toast.error(error?.response?.data?.detail?.message || error?.response?.data?.detail || "User could not be saved."); }
    finally { setSaving(false); }
  }

  async function remove(id:number) {
    if(!window.confirm("Delete this user? This action cannot be undone.")) return;
    try { await userApi.remove(id); await qc.invalidateQueries({queryKey:userKeys.all}); toast.success("User deleted."); }
    catch(error:any){toast.error(error?.response?.data?.detail||"User could not be deleted.");}
  }

  async function removeSelected() {
    if (!selectedIds.length || !window.confirm(`Delete ${selectedIds.length} selected users? This action cannot be undone.`)) return;
    setDeleting(true);
    let deleted = 0;
    let failed = 0;
    for (const id of selectedIds) {
      try { await userApi.remove(id); deleted += 1; }
      catch { failed += 1; }
    }
    setSelectedIds([]);
    await qc.invalidateQueries({ queryKey:userKeys.all });
    if (deleted) toast.success(`${deleted} user${deleted === 1 ? "" : "s"} deleted.`);
    if (failed) toast.error(`${failed} user${failed === 1 ? "" : "s"} could not be deleted.`);
    setDeleting(false);
  }

  function toggleVisible(checked:boolean) {
    setSelectedIds((current) => checked
      ? Array.from(new Set([...current, ...selectableIds]))
      : current.filter((id) => !selectableIds.includes(id)));
  }

  return <div className="space-y-6">
    <PageHeader title="Users" description="Create, update, deactivate, delete and assign roles to system users." actions={<Button onClick={()=>setEditor("new")}><Plus size={16}/> Create User</Button>}/>
    <Card>
      <div className="mb-5 flex flex-wrap items-center gap-3"><div className="relative max-w-md flex-1"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400"/><Input className="pl-9" value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search users..."/></div>{selectedIds.length>0&&<Button variant="danger" loading={deleting} onClick={removeSelected}><Trash2 size={16}/> Delete Selected ({selectedIds.length})</Button>}</div>
      {users.isLoading?<div className="py-12"><Loading/></div>:users.isError?<div className="py-10 text-center text-sm text-red-600">Users could not be loaded.</div>:visibleUsers.length===0?<div className="py-12 text-center"><Users className="mx-auto mb-2 h-8 w-8 text-slate-400"/><p>No users found.</p></div>:<><div className={users.isFetching ? "opacity-70" : ""}><Table className="min-w-[820px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH><input type="checkbox" aria-label="Select all visible users" checked={allVisibleSelected} onChange={(e)=>toggleVisible(e.target.checked)}/></TH><TH>User</TH><TH>Organization</TH><TH>Roles</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead><TBody>{visibleUsers.map((user)=><TR key={user.id}><TD><input type="checkbox" aria-label={`Select ${user.full_name}`} disabled={user.id===(currentUser as any)?.id} checked={selectedIds.includes(user.id)} onChange={(e)=>setSelectedIds((current)=>e.target.checked?[...current,user.id]:current.filter((id)=>id!==user.id))}/></TD><TD className="max-w-[260px]"><TableCellStack primary={user.full_name} secondary={`${user.username} · ${user.email}`}/></TD><TD>{user.department?.name || user.location?.name ? <TableCellStack primary={user.department?.name || user.location?.name} secondary={user.department?.name ? user.location?.name : undefined}/> : "—"}</TD><TD><div className="flex max-w-sm flex-wrap gap-1">{user.roles.map((role)=><Badge key={role.id} variant="outline">{role.name}</Badge>)}</div></TD><TD><Badge variant={user.is_active?"success":"secondary"}>{user.is_active?"Active":"Inactive"}</Badge></TD><TD><div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={()=>setEditor(user.id)}><Pencil size={14}/> Edit</Button><Button size="sm" variant="danger" disabled={user.id===(currentUser as any)?.id} onClick={()=>remove(user.id)}><Trash2 size={14}/> Delete</Button></div></TD></TR>)}</TBody></Table></div><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="users" onChange={setPage}/></>}
    </Card>
    <Dialog open={editor!==null} onOpenChange={(open)=>!open&&setEditor(null)}><DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto"><DialogHeader><DialogTitle>{editor==="new"?"Create User":"Edit User"}</DialogTitle></DialogHeader><DialogBody className="space-y-4">{typeof editor==="number"&&detail.isLoading?<Loading/>:<><div className="grid gap-4 sm:grid-cols-2"><div><Label required>Username</Label><Input value={username} onChange={(e)=>setUsername(e.target.value)}/></div><div><Label required>Full Name</Label><Input value={fullName} onChange={(e)=>setFullName(e.target.value)}/></div><div><Label required>Email</Label><Input type="email" value={email} onChange={(e)=>setEmail(e.target.value)}/></div><div><Label required={editor==="new"}>{editor==="new"?"Password":"New Password"}</Label><Input type="password" value={password} onChange={(e)=>setPassword(e.target.value)} placeholder={editor==="new"?"Minimum 8 characters":"Leave blank to keep current password"}/></div><div><Label>Department</Label><select className="mt-1 h-10 w-full rounded-md border px-3" value={departmentId} onChange={(e)=>setDepartmentId(e.target.value)}><option value="">None</option>{(departments.data??[]).map((d)=><option key={d.id} value={d.id}>{d.code} - {d.name}</option>)}</select></div><div><Label>Location</Label><select className="mt-1 h-10 w-full rounded-md border px-3" value={locationId} onChange={(e)=>setLocationId(e.target.value)}><option value="">None</option>{(locations.data??[]).map((l)=><option key={l.id} value={l.id}>{l.code} - {l.name}</option>)}</select></div></div><label className="flex items-center gap-2"><input type="checkbox" checked={isActive} onChange={(e)=>setIsActive(e.target.checked)}/> Active user</label><div><Label>Roles</Label><div className="mt-2 grid gap-2 sm:grid-cols-2">{(roles.data??[]).map((role)=><label key={role.id} className="flex items-center gap-2 rounded border p-3 text-sm"><input type="checkbox" checked={roleIds.includes(role.id)} onChange={(e)=>setRoleIds((current)=>e.target.checked?[...current,role.id]:current.filter((id)=>id!==role.id))}/><span>{role.name}</span></label>)}</div></div></>}</DialogBody><DialogFooter><Button variant="outline" onClick={()=>setEditor(null)}>Cancel</Button><Button loading={saving} onClick={save}>{editor==="new"?"Create User":"Save Changes"}</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}

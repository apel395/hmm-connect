import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Label from "@/components/ui/Label";
import Loading from "@/components/ui/Loading";
import useAuthStore from "@/store/auth";
import { userApi } from "./userApi";
import { useAssignableDepartments, useAssignableLocations, useAssignableRoles, useUserDetail, useUsers, userKeys } from "./useUsers";

export default function UserPage() {
  const qc = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const users = useUsers();
  const [search, setSearch] = useState("");
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

  useEffect(() => {
    if (editor === "new") { setUsername(""); setEmail(""); setFullName(""); setPassword(""); setIsActive(true); setDepartmentId(""); setLocationId(""); setRoleIds([]); return; }
    if (!detail.data) return;
    setUsername(detail.data.username); setEmail(detail.data.email); setFullName(detail.data.full_name); setPassword(""); setIsActive(detail.data.is_active); setDepartmentId(detail.data.department_id ? String(detail.data.department_id) : ""); setLocationId(detail.data.location_id ? String(detail.data.location_id) : ""); setRoleIds(detail.data.role_ids);
  }, [detail.data, editor]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (users.data ?? []).filter((user) => [user.username,user.full_name,user.email,user.department?.name,user.location?.name,...user.roles.map((r)=>r.name)].filter(Boolean).join(" ").toLowerCase().includes(term));
  }, [search, users.data]);

  async function save() {
    if (!username.trim() || !email.trim() || !fullName.trim()) return toast.error("Username, email and full name are required.");
    if (editor === "new" && password.length < 8) return toast.error("Password must be at least 8 characters.");
    setSaving(true);
    try {
      if (editor === "new") {
        await userApi.create({ username:username.trim(), email:email.trim(), full_name:fullName.trim(), password, is_active:isActive, department_id:departmentId?Number(departmentId):null, location_id:locationId?Number(locationId):null, role_ids:roleIds });
      } else if (typeof editor === "number") {
        await userApi.update(editor,{ username:username.trim(), email:email.trim(), full_name:fullName.trim(), is_active:isActive, department_id:departmentId?Number(departmentId):null, location_id:locationId?Number(locationId):null });
        await userApi.replaceRoles(editor,roleIds);
      }
      await qc.invalidateQueries({queryKey:userKeys.list()}); toast.success(editor==="new"?"User created.":"User updated."); setEditor(null);
    } catch (error:any) { toast.error(error?.response?.data?.detail?.message || error?.response?.data?.detail || "User could not be saved."); }
    finally { setSaving(false); }
  }

  async function remove(id:number) {
    if(!window.confirm("Delete this user? This action cannot be undone.")) return;
    try { await userApi.remove(id); await qc.invalidateQueries({queryKey:userKeys.list()}); toast.success("User deleted."); }
    catch(error:any){toast.error(error?.response?.data?.detail||"User could not be deleted.");}
  }

  return <div className="space-y-6">
    <PageHeader title="Users" description="Create, update, deactivate, delete and assign roles to system users." actions={<Button onClick={()=>setEditor("new")}><Plus size={16}/> Create User</Button>}/>
    <Card>
      <div className="relative mb-5 max-w-md"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400"/><Input className="pl-9" value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search users..."/></div>
      {users.isLoading?<div className="py-12"><Loading/></div>:users.isError?<div className="py-10 text-center text-sm text-red-600">Users could not be loaded.</div>:filtered.length===0?<div className="py-12 text-center"><Users className="mx-auto mb-2 h-8 w-8 text-slate-400"/><p>No users found.</p></div>:<div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="border-b text-xs uppercase text-slate-500"><tr><th className="pb-3">Username</th><th className="pb-3">Name</th><th className="pb-3">Department</th><th className="pb-3">Location</th><th className="pb-3">Roles</th><th className="pb-3">Status</th><th className="pb-3 text-right">Actions</th></tr></thead><tbody className="divide-y">{filtered.map((user)=><tr key={user.id}><td className="py-4 font-semibold">{user.username}</td><td className="py-4"><div>{user.full_name}</div><div className="text-xs text-slate-500">{user.email}</div></td><td>{user.department?.name||"—"}</td><td>{user.location?.name||"—"}</td><td><div className="flex flex-wrap gap-1">{user.roles.map((role)=><Badge key={role.id} variant="outline">{role.name}</Badge>)}</div></td><td><Badge variant={user.is_active?"success":"secondary"}>{user.is_active?"Active":"Inactive"}</Badge></td><td><div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={()=>setEditor(user.id)}><Pencil size={14}/> Edit</Button><Button size="sm" variant="danger" disabled={user.id===(currentUser as any)?.id} onClick={()=>remove(user.id)}><Trash2 size={14}/> Delete</Button></div></td></tr>)}</tbody></table></div>}
    </Card>
    <Dialog open={editor!==null} onOpenChange={(open)=>!open&&setEditor(null)}><DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto"><DialogHeader><DialogTitle>{editor==="new"?"Create User":"Edit User"}</DialogTitle></DialogHeader><DialogBody className="space-y-4">{typeof editor==="number"&&detail.isLoading?<Loading/>:<><div className="grid gap-4 sm:grid-cols-2"><div><Label required>Username</Label><Input value={username} onChange={(e)=>setUsername(e.target.value)}/></div><div><Label required>Full Name</Label><Input value={fullName} onChange={(e)=>setFullName(e.target.value)}/></div><div><Label required>Email</Label><Input type="email" value={email} onChange={(e)=>setEmail(e.target.value)}/></div>{editor==="new"&&<div><Label required>Password</Label><Input type="password" value={password} onChange={(e)=>setPassword(e.target.value)} placeholder="Minimum 8 characters"/></div>}<div><Label>Department</Label><select className="mt-1 h-10 w-full rounded-md border px-3" value={departmentId} onChange={(e)=>setDepartmentId(e.target.value)}><option value="">None</option>{(departments.data??[]).map((d)=><option key={d.id} value={d.id}>{d.code} - {d.name}</option>)}</select></div><div><Label>Location</Label><select className="mt-1 h-10 w-full rounded-md border px-3" value={locationId} onChange={(e)=>setLocationId(e.target.value)}><option value="">None</option>{(locations.data??[]).map((l)=><option key={l.id} value={l.id}>{l.code} - {l.name}</option>)}</select></div></div><label className="flex items-center gap-2"><input type="checkbox" checked={isActive} onChange={(e)=>setIsActive(e.target.checked)}/> Active user</label><div><Label>Roles</Label><div className="mt-2 grid gap-2 sm:grid-cols-2">{(roles.data??[]).map((role)=><label key={role.id} className="flex items-center gap-2 rounded border p-3 text-sm"><input type="checkbox" checked={roleIds.includes(role.id)} onChange={(e)=>setRoleIds((current)=>e.target.checked?[...current,role.id]:current.filter((id)=>id!==role.id))}/><span>{role.name}</span></label>)}</div></div></>}</DialogBody><DialogFooter><Button variant="outline" onClick={()=>setEditor(null)}>Cancel</Button><Button loading={saving} onClick={save}>{editor==="new"?"Create User":"Save Changes"}</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}

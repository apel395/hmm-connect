import { useState } from "react";
import { Pencil, Plus, Shield, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { getRoles, createRole, deleteRole, updateRole, type Role } from "../features/roles/rolesApi";

export default function RolesPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [deleting, setDeleting] = useState<Role | null>(null);

  const rolesQuery = useQuery({ queryKey: ["roles"], queryFn: getRoles });
  const deleteMutation = useMutation({ mutationFn: deleteRole, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["roles"] }); setDeleting(null); } });

  return (
    <div className="space-y-6">
      <PageHeader title="Roles" description="Manage user roles and access levels." actions={<Button onClick={() => { setEditing(null); setFormOpen(true); }}><Plus size={18} /> Create role</Button>} />
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-6"><h2 className="font-semibold text-slate-900">All roles</h2></div>
        {rolesQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading roles...</div>}
        {rolesQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load roles.</div>}
        {!rolesQuery.isLoading && !rolesQuery.isError && !rolesQuery.data?.length && <EmptyState title="No roles found" description="Create a role to define the ERP identity model." action={<Button onClick={() => setFormOpen(true)}><Plus size={18} /> Create role</Button>} />}
        {!!rolesQuery.data?.length && <div className="divide-y divide-slate-100">{rolesQuery.data.map((role) => <div key={role.id} className="flex items-center justify-between p-5"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100"><Shield size={18} className="text-slate-600" /></div><div><p className="font-medium text-slate-900">{role.name}</p><p className="mt-1 text-sm text-slate-500">{role.description || "No description"}</p></div></div><div className="flex items-center gap-2"><Button variant="ghost" onClick={() => { setEditing(role); setFormOpen(true); }}><Pencil size={16} /> Edit</Button><Button variant="ghost" onClick={() => setDeleting(role)}><Trash2 size={16} className="text-red-600" /></Button></div></div>)}</div>}
      </div>
      <RoleModal key={editing?.id ?? "new"} open={formOpen} role={editing} onClose={() => setFormOpen(false)} />
      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && deleteMutation.mutate(deleting.id)} title="Delete role?" description={`Delete ${deleting?.name ?? "this role"}?`} confirmLabel="Delete role" danger loading={deleteMutation.isPending} />
    </div>
  );
}

function RoleModal({ open, role, onClose }: { open: boolean; role: Role | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");

  const mutation = useMutation({
    mutationFn: () => role ? updateRole(role.id, { name, description }) : createRole({ name, description }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["roles"] }); onClose(); },
  });

  return <Modal open={open} onClose={onClose} title={role ? "Edit role" : "Create role"} description="Roles are part of the audit identity context." footer={<><Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>Cancel</Button><Button type="button" onClick={() => mutation.mutate()} loading={mutation.isPending}>{role ? "Save changes" : "Create role"}</Button></>}><div className="space-y-4"><Input label="Role name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Purchasing" /><div className="space-y-2"><label className="block text-sm font-medium text-slate-700">Description</label><textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-900" /></div>{mutation.isError && <p className="text-sm text-red-600">Failed to save role.</p>}</div></Modal>;
}

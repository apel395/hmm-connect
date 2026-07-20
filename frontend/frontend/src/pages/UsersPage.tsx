import { useMemo, useState } from "react";
import { MoreHorizontal, Plus, Search } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";

import {
  assignDepartment,
  assignLocation,
  assignRole,
  createUser,
  getUsers,
  type User,
} from "../features/users/usersApi";
import { getRoles } from "../features/roles/rolesApi";
import { getDepartments } from "../features/departments/departmentsApi";
import { getLocations } from "../features/locations/locationsApi";

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [menuUserId, setMenuUserId] = useState<number | null>(null);

  const usersQuery = useQuery({ queryKey: ["users"], queryFn: getUsers });
  const rolesQuery = useQuery({ queryKey: ["roles"], queryFn: getRoles });
  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: getDepartments });
  const locationsQuery = useQuery({ queryKey: ["locations"], queryFn: getLocations });

  const assignRoleMutation = useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number }) => assignRole(userId, roleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const assignDepartmentMutation = useMutation({
    mutationFn: ({ userId, departmentId }: { userId: number; departmentId: number | null }) => assignDepartment(userId, departmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const assignLocationMutation = useMutation({
    mutationFn: ({ userId, locationId }: { userId: number; locationId: number | null }) => assignLocation(userId, locationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const users = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const list = usersQuery.data ?? [];
    if (!normalized) return list;
    return list.filter((user) =>
      [user.full_name, user.username, user.email, user.department?.name, user.location?.name]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(normalized)),
    );
  }, [search, usersQuery.data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Manage users and their audit identity context."
        actions={<Button onClick={() => setCreateOpen(true)}><Plus size={18} /> Add user</Button>}
      />

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex w-full max-w-md items-center gap-2 rounded-lg bg-slate-100 px-3 py-2">
            <Search size={18} className="text-slate-400" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search users..." className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400" />
          </div>
          <div className="text-sm text-slate-500">{users.length} users</div>
        </div>

        {usersQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading users...</div>}
        {usersQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load users.</div>}

        {!usersQuery.isLoading && !usersQuery.isError && users.length === 0 && (
          <EmptyState title="No users found" description="Create your first user to get started." action={<Button onClick={() => setCreateOpen(true)}><Plus size={18} /> Add user</Button>} />
        )}

        {users.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px]">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  {['User', 'Department', 'Location', 'Roles', 'Actions'].map((label, index) => (
                    <th key={label} className={`px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500 ${index === 4 ? 'text-right' : ''}`}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    roles={rolesQuery.data ?? []}
                    departments={departmentsQuery.data ?? []}
                    locations={locationsQuery.data ?? []}
                    menuOpen={menuUserId === user.id}
                    onMenu={() => setMenuUserId(menuUserId === user.id ? null : user.id)}
                    onAssignRole={(roleId) => assignRoleMutation.mutate({ userId: user.id, roleId })}
                    onAssignDepartment={(departmentId) => assignDepartmentMutation.mutate({ userId: user.id, departmentId })}
                    onAssignLocation={(locationId) => assignLocationMutation.mutate({ userId: user.id, locationId })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateUserModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

function UserRow({
  user,
  roles,
  departments,
  locations,
  menuOpen,
  onMenu,
  onAssignRole,
  onAssignDepartment,
  onAssignLocation,
}: {
  user: User;
  roles: { id: number; name: string }[];
  departments: { id: number; name: string }[];
  locations: { id: number; code: string; name: string }[];
  menuOpen: boolean;
  onMenu: () => void;
  onAssignRole: (roleId: number) => void;
  onAssignDepartment: (departmentId: number | null) => void;
  onAssignLocation: (locationId: number | null) => void;
}) {
  const availableRoles = roles.filter((role) => !user.roles.some((userRole) => userRole.id === role.id));

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-700">{user.full_name.charAt(0).toUpperCase()}</div>
          <div>
            <p className="text-sm font-medium text-slate-900">{user.full_name}</p>
            <p className="text-xs text-slate-500">@{user.username} · {user.email}</p>
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <Select value={String(user.department_id ?? '')} onChange={(value) => onAssignDepartment(value ? Number(value) : null)} options={departments.map((department) => ({ value: String(department.id), label: department.name }))} placeholder="No department" className="w-48" />
      </td>
      <td className="px-6 py-4">
        <Select value={String(user.location_id ?? '')} onChange={(value) => onAssignLocation(value ? Number(value) : null)} options={locations.map((location) => ({ value: String(location.id), label: `${location.code} · ${location.name}` }))} placeholder="No location" className="w-56" />
      </td>
      <td className="px-6 py-4">
        <div className="flex max-w-[300px] flex-wrap items-center gap-2">
          {user.roles.map((role) => <span key={role.id} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{role.name}</span>)}
          <Select value="" onChange={(value) => value && onAssignRole(Number(value))} options={availableRoles.map((role) => ({ value: String(role.id), label: role.name }))} placeholder="+ Role" className="w-28" />
        </div>
      </td>
      <td className="relative px-6 py-4 text-right">
        <button type="button" onClick={onMenu} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"><MoreHorizontal size={18} /></button>
        {menuOpen && <div className="absolute right-6 top-14 z-20 w-48 rounded-xl border border-slate-200 bg-white p-2 text-left shadow-xl"><div className="px-3 py-2 text-xs text-slate-500">Audit context</div><div className="px-3 py-2 text-sm text-slate-700">{user.department?.name ?? 'No department'}</div><div className="px-3 py-2 text-sm text-slate-700">{user.location?.name ?? 'No location'}</div></div>}
      </td>
    </tr>
  );
}

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [roleId, setRoleId] = useState("");

  const rolesQuery = useQuery({ queryKey: ["roles"], queryFn: getRoles });
  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: getDepartments });
  const locationsQuery = useQuery({ queryKey: ["locations"], queryFn: getLocations });

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setUsername(""); setEmail(""); setFullName(""); setPassword(""); setDepartmentId(""); setLocationId(""); setRoleId("");
      onClose();
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Create user" description="Create a user and define the context captured in future audit events." size="lg" footer={<><Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>Cancel</Button><Button type="button" onClick={() => mutation.mutate({ username, email, full_name: fullName, password, department_id: departmentId ? Number(departmentId) : undefined, location_id: locationId ? Number(locationId) : undefined, role_id: roleId ? Number(roleId) : undefined })} loading={mutation.isPending}>Create user</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Full name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Advan" />
        <Input label="Username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="advan" />
        <Input label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="user@company.com" />
        <Input label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Minimum 8 characters" />
        <div className="space-y-2"><label className="block text-sm font-medium text-slate-700">Department</label><Select value={departmentId} onChange={setDepartmentId} options={(departmentsQuery.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))} placeholder="Select department" /></div>
        <div className="space-y-2"><label className="block text-sm font-medium text-slate-700">Location</label><Select value={locationId} onChange={setLocationId} options={(locationsQuery.data ?? []).map((item) => ({ value: String(item.id), label: `${item.code} · ${item.name}` }))} placeholder="Select location" /></div>
        <div className="space-y-2 sm:col-span-2"><label className="block text-sm font-medium text-slate-700">Initial role</label><Select value={roleId} onChange={setRoleId} options={(rolesQuery.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))} placeholder="Select role" /></div>
      </div>
      {mutation.isError && <p className="mt-4 text-sm text-red-600">Failed to create user. Check the entered data.</p>}
    </Modal>
  );
}

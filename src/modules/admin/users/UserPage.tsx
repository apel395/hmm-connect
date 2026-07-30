import { useMemo, useState } from "react";
import axios from "axios";
import { Eye, Search, Users } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import type { AdminUser } from "./types";
import { useUsers } from "./useUsers";

type StatusFilter = "ALL" | "ACTIVE" | "INACTIVE";

function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Users could not be loaded.";
  if (error.response?.status === 403) {
    return "Administrator access is required to view users.";
  }
  if (error.response?.status && error.response.status >= 500) {
    return "The server could not load users.";
  }
  return "Users could not be loaded.";
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("id-ID");
}

export default function UserPage() {
  const users = useUsers();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [department, setDepartment] = useState("ALL");
  const [location, setLocation] = useState("ALL");
  const [role, setRole] = useState("ALL");
  const [selected, setSelected] = useState<AdminUser | null>(null);

  const filterOptions = useMemo(() => {
    const data = users.data ?? [];
    return {
      departments: [...new Map(
        data
          .filter((user) => user.department)
          .map((user) => [user.department!.id, user.department!]),
      ).values()].sort((a, b) => a.name.localeCompare(b.name)),
      locations: [...new Map(
        data
          .filter((user) => user.location)
          .map((user) => [user.location!.id, user.location!]),
      ).values()].sort((a, b) => a.name.localeCompare(b.name)),
      roles: [...new Set(data.flatMap((user) => user.roles.map((item) => item.name)))]
        .sort((a, b) => a.localeCompare(b)),
    };
  }, [users.data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (users.data ?? []).filter((user) => {
      const matchesSearch =
        !term ||
        [
          user.username,
          user.full_name,
          user.email,
          user.department?.name,
          user.location?.name,
          ...user.roles.map((item) => item.name),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(term);
      const matchesStatus =
        status === "ALL" ||
        (status === "ACTIVE" ? user.is_active : !user.is_active);
      const matchesDepartment =
        department === "ALL" || String(user.department_id) === department;
      const matchesLocation =
        location === "ALL" || String(user.location_id) === location;
      const matchesRole =
        role === "ALL" || user.roles.some((item) => item.name === role);
      return (
        matchesSearch &&
        matchesStatus &&
        matchesDepartment &&
        matchesLocation &&
        matchesRole
      );
    });
  }, [department, location, role, search, status, users.data]);

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          title="Users"
          description="Review system users, organizational assignments, and access roles."
        />

        <Card>
          <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input
                type="search"
                aria-label="Search users"
                placeholder="Search users..."
                value={search}
                className="pl-9"
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <select
              aria-label="Filter by status"
              value={status}
              className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              onChange={(event) => setStatus(event.target.value as StatusFilter)}
            >
              <option value="ALL">All statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </select>
            <select
              aria-label="Filter by department"
              value={department}
              className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              onChange={(event) => setDepartment(event.target.value)}
            >
              <option value="ALL">All departments</option>
              {filterOptions.departments.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            <select
              aria-label="Filter by location"
              value={location}
              className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              onChange={(event) => setLocation(event.target.value)}
            >
              <option value="ALL">All locations</option>
              {filterOptions.locations.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            <select
              aria-label="Filter by role"
              value={role}
              className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="ALL">All roles</option>
              {filterOptions.roles.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </div>

          {users.isLoading ? (
            <div className="py-12"><Loading /></div>
          ) : users.isError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <p className="text-sm text-red-700">{errorMessage(users.error)}</p>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => users.refetch()}>
                Try Again
              </Button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center">
              <Users className="mx-auto mb-2 h-8 w-8 text-slate-400" />
              <p className="text-sm font-medium">No users match the filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1050px] text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="pb-3 font-medium">Username</th>
                    <th className="pb-3 font-medium">Full Name</th>
                    <th className="pb-3 font-medium">Email</th>
                    <th className="pb-3 font-medium">Department</th>
                    <th className="pb-3 font-medium">Location</th>
                    <th className="pb-3 font-medium">Roles</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Created</th>
                    <th className="pb-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50">
                      <td className="py-4 pr-3 font-semibold">{user.username}</td>
                      <td className="py-4 pr-3">{user.full_name}</td>
                      <td className="py-4 pr-3">{user.email}</td>
                      <td className="py-4 pr-3">{user.department?.name || "—"}</td>
                      <td className="py-4 pr-3">{user.location?.name || "—"}</td>
                      <td className="py-4 pr-3">
                        <div className="flex max-w-64 flex-wrap gap-1">
                          {user.roles.length
                            ? user.roles.map((item) => (
                                <Badge key={item.id} variant="primary">{item.name}</Badge>
                              ))
                            : <span className="text-slate-400">No roles</span>}
                        </div>
                      </td>
                      <td className="py-4 pr-3">
                        <Badge variant={user.is_active ? "success" : "secondary"}>
                          {user.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="py-4 pr-3">{formatDate(user.created_at)}</td>
                      <td className="py-4 text-right">
                        <Button size="sm" variant="outline" onClick={() => setSelected(user)}>
                          <Eye className="h-4 w-4" /> View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>User Details</DialogTitle></DialogHeader>
          <DialogBody>
            {selected && (
              <dl className="grid gap-5 sm:grid-cols-2">
                {[
                  ["Username", selected.username],
                  ["Full Name", selected.full_name],
                  ["Email", selected.email],
                  ["Department", selected.department?.name],
                  ["Location", selected.location?.name],
                  ["Created", formatDate(selected.created_at)],
                  ["Updated", formatDate(selected.updated_at)],
                ].filter((field) => field[1]).map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs uppercase text-slate-500">{label}</dt>
                    <dd className="mt-1 text-sm font-medium">{value}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-xs uppercase text-slate-500">Status</dt>
                  <dd className="mt-1">
                    <Badge variant={selected.is_active ? "success" : "secondary"}>
                      {selected.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </dd>
                </div>
                {selected.roles.length > 0 && (
                  <div className="sm:col-span-2">
                    <dt className="text-xs uppercase text-slate-500">Assigned Roles</dt>
                    <dd className="mt-2 flex flex-wrap gap-1">
                      {selected.roles.map((item) => <Badge key={item.id}>{item.name}</Badge>)}
                    </dd>
                  </div>
                )}
              </dl>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

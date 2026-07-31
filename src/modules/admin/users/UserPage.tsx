import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Pencil, Search, Users } from "lucide-react";
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
import Label from "@/components/ui/Label";
import Loading from "@/components/ui/Loading";
import useAuthStore from "@/store/auth";
import type { UserDetailsUpdate } from "./types";
import { userApi } from "./userApi";
import {
  useAssignableDepartments,
  useAssignableLocations,
  useAssignableRoles,
  useUserDetail,
  useUsers,
  userKeys,
} from "./useUsers";

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

function saveErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "The user could not be saved.";
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String(detail.message);
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg)
      .filter(Boolean)
      .join(" ") || "Please check the user details.";
  }
  return "The user could not be saved.";
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("id-ID");
}

export default function UserPage() {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const users = useUsers();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [department, setDepartment] = useState("ALL");
  const [location, setLocation] = useState("ALL");
  const [role, setRole] = useState("ALL");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const userDetail = useUserDetail(selectedUserId);
  const roles = useAssignableRoles(selectedUserId !== null);
  const departments = useAssignableDepartments(selectedUserId !== null);
  const locations = useAssignableLocations(selectedUserId !== null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [departmentId, setDepartmentId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState("");

  useEffect(() => {
    if (!userDetail.data) return;
    setUsername(userDetail.data.username);
    setEmail(userDetail.data.email);
    setFullName(userDetail.data.full_name);
    setIsActive(userDetail.data.is_active);
    setDepartmentId(
      userDetail.data.department_id == null
        ? ""
        : String(userDetail.data.department_id),
    );
    setLocationId(
      userDetail.data.location_id == null
        ? ""
        : String(userDetail.data.location_id),
    );
    setRoleIds(userDetail.data.role_ids);
    setSaveError("");
    setSaveSuccess("");
  }, [userDetail.data]);

  function closeEditor() {
    if (saving) return;
    setSelectedUserId(null);
    setSaveError("");
    setSaveSuccess("");
  }

  async function saveUser() {
    const detail = userDetail.data;
    if (!detail || selectedUserId === null) return;

    const normalizedUsername = username.trim();
    const normalizedEmail = email.trim().toLowerCase();
    const normalizedFullName = fullName.trim();
    if (!normalizedUsername || !normalizedEmail || !normalizedFullName) {
      setSaveError("Username, email, and full name are required.");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalizedEmail)) {
      setSaveError("Enter a valid email address.");
      return;
    }

    const detailsUpdate: UserDetailsUpdate = {};
    if (normalizedUsername !== detail.username) {
      detailsUpdate.username = normalizedUsername;
    }
    if (normalizedEmail !== detail.email) detailsUpdate.email = normalizedEmail;
    if (normalizedFullName !== detail.full_name) {
      detailsUpdate.full_name = normalizedFullName;
    }
    if (isActive !== detail.is_active) detailsUpdate.is_active = isActive;
    const nextDepartmentId = departmentId ? Number(departmentId) : null;
    if (nextDepartmentId !== detail.department_id) {
      detailsUpdate.department_id = nextDepartmentId;
    }
    const nextLocationId = locationId ? Number(locationId) : null;
    if (nextLocationId !== detail.location_id) {
      detailsUpdate.location_id = nextLocationId;
    }
    const currentRoleIds = [...detail.role_ids].sort((a, b) => a - b);
    const nextRoleIds = [...roleIds].sort((a, b) => a - b);
    const rolesChanged =
      currentRoleIds.length !== nextRoleIds.length ||
      currentRoleIds.some((id, index) => id !== nextRoleIds[index]);
    const detailsChanged = Object.keys(detailsUpdate).length > 0;

    setSaving(true);
    setSaveError("");
    setSaveSuccess("");
    let detailsSaved = false;
    try {
      if (detailsChanged) {
        await userApi.update(selectedUserId, detailsUpdate);
        detailsSaved = true;
      }
      if (rolesChanged) {
        await userApi.replaceRoles(selectedUserId, nextRoleIds);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: userKeys.list() }),
        queryClient.invalidateQueries({ queryKey: userKeys.detail(selectedUserId) }),
      ]);
      await userDetail.refetch();
      setSaveSuccess(
        detailsChanged || rolesChanged ? "User saved successfully." : "No changes to save.",
      );
    } catch (error) {
      if (detailsSaved && rolesChanged) {
        setSaveError(
          `User details were saved, but roles were not updated. ${saveErrorMessage(error)}`,
        );
        await queryClient.invalidateQueries({ queryKey: userKeys.list() });
        await userDetail.refetch();
      } else {
        setSaveError(saveErrorMessage(error));
      }
    } finally {
      setSaving(false);
    }
  }

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
                        <Button size="sm" variant="outline" onClick={() => setSelectedUserId(user.id)}>
                          <Pencil className="h-4 w-4" /> Edit
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

      <Dialog open={selectedUserId !== null} onOpenChange={(open) => !open && closeEditor()}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Edit User</DialogTitle></DialogHeader>
          <DialogBody className="space-y-5">
            {userDetail.isLoading ? (
              <div className="py-10"><Loading /></div>
            ) : userDetail.isError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {saveErrorMessage(userDetail.error)}
              </div>
            ) : userDetail.data ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label required>Username</Label>
                    <Input value={username} onChange={(event) => setUsername(event.target.value)} />
                  </div>
                  <div>
                    <Label required>Email</Label>
                    <Input
                      type="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <Label required>Full name</Label>
                    <Input value={fullName} onChange={(event) => setFullName(event.target.value)} />
                  </div>
                  <div>
                    <Label>Department</Label>
                    <select
                      className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                      value={departmentId}
                      onChange={(event) => setDepartmentId(event.target.value)}
                    >
                      <option value="">No department</option>
                      {departments.data?.map((item) => (
                        <option key={item.id} value={item.id}>{item.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label>Location</Label>
                    <select
                      className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                      value={locationId}
                      onChange={(event) => setLocationId(event.target.value)}
                    >
                      <option value="">No location</option>
                      {locations.data?.map((item) => (
                        <option key={item.id} value={item.id}>{item.name}</option>
                      ))}
                    </select>
                  </div>
                  <label className="flex items-center gap-3 sm:col-span-2">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300"
                      checked={isActive}
                      onChange={(event) => setIsActive(event.target.checked)}
                    />
                    <span>
                      <span className="block text-sm font-medium text-slate-700">Active user</span>
                      <span className="block text-xs text-slate-500">
                        Inactive users cannot sign in.
                        {currentUser?.id === selectedUserId && " You cannot deactivate your own account."}
                      </span>
                    </span>
                  </label>
                </div>

                <div>
                  <Label>Assigned roles</Label>
                  <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                    {roles.isLoading ? (
                      <div className="py-3"><Loading /></div>
                    ) : roles.data?.length ? (
                      roles.data.map((item) => (
                        <label key={item.id} className="flex items-start gap-3 rounded-md p-2 hover:bg-slate-50">
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-slate-300"
                            checked={roleIds.includes(item.id)}
                            onChange={(event) => {
                              setRoleIds((current) =>
                                event.target.checked
                                  ? [...current, item.id]
                                  : current.filter((id) => id !== item.id),
                              );
                            }}
                          />
                          <span>
                            <span className="block text-sm font-medium">{item.name}</span>
                            {item.description && (
                              <span className="block text-xs text-slate-500">{item.description}</span>
                            )}
                          </span>
                        </label>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No roles are available.</p>
                    )}
                  </div>
                </div>

                {(roles.isError || departments.isError || locations.isError) && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    Some assignment options could not be loaded. Close and try again.
                  </div>
                )}
                {saveError && (
                  <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {saveError}
                  </div>
                )}
                {saveSuccess && (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                    {saveSuccess}
                  </div>
                )}
              </>
            ) : null}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" disabled={saving} onClick={closeEditor}>Cancel</Button>
            <Button
              loading={saving}
              disabled={
                !userDetail.data ||
                roles.isLoading ||
                departments.isLoading ||
                locations.isLoading ||
                roles.isError ||
                departments.isError ||
                locations.isError
              }
              onClick={saveUser}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

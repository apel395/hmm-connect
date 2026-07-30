import { useMemo, useState } from "react";
import { KeyRound, Search } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import useAuthStore from "@/store/auth";

export default function RolePage() {
  const user = useAuthStore((state) => state.user);
  const [search, setSearch] = useState("");
  const roles = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (user?.roles ?? []).filter((role) =>
      [role.name, role.description, ...(role.permissions ?? []).map((item) => item.code)]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [search, user?.roles]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Roles"
        description="Review role definitions and permissions visible to the current account."
      />
      <Card>
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-md">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              type="search"
              placeholder="Search roles or permissions..."
              value={search}
              className="pl-9"
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Badge variant="warning">Current account roles</Badge>
        </div>

        {roles.length === 0 ? (
          <div className="py-12 text-center">
            <KeyRound className="mx-auto mb-2 h-8 w-8 text-slate-400" />
            <p className="text-sm text-slate-500">No visible roles match the search.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="border-b text-xs uppercase text-slate-500">
                <tr>
                  <th className="pb-3 font-medium">Role Name</th>
                  <th className="pb-3 font-medium">Description</th>
                  <th className="pb-3 font-medium">Permission Count</th>
                  <th className="pb-3 font-medium">Permissions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {roles.map((role) => (
                  <tr key={role.name}>
                    <td className="py-4 font-semibold">{role.name}</td>
                    <td className="py-4 text-slate-600">{role.description || "—"}</td>
                    <td className="py-4">{role.permissions?.length ?? 0}</td>
                    <td className="py-4">
                      <div className="flex max-w-xl flex-wrap gap-1">
                        {(role.permissions ?? []).map((permission) => (
                          <Badge key={permission.code} variant="outline" title={permission.description || undefined}>
                            {permission.code}
                          </Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

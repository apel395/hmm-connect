import { useMemo, useState } from "react";
import {
  Building2,
  KeyRound,
  MapPin,
  ShieldCheck,
  Warehouse,
} from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import useAuthStore from "@/store/auth";

type Section = "roles" | "permissions" | "departments" | "locations" | "warehouses";

const sections = [
  { id: "roles", label: "Roles", icon: ShieldCheck },
  { id: "permissions", label: "Permissions", icon: KeyRound },
  { id: "departments", label: "Departments", icon: Building2 },
  { id: "locations", label: "Locations", icon: MapPin },
  { id: "warehouses", label: "Warehouses", icon: Warehouse },
] as const;

export default function SettingPage() {
  const [section, setSection] = useState<Section>("roles");
  const user = useAuthStore((state) => state.user);
  const permissions = useMemo(() => {
    const map = new Map<string, { code: string; description?: string | null }>();
    for (const role of user?.roles ?? []) {
      for (const permission of role.permissions ?? []) map.set(permission.code, permission);
    }
    return [...map.values()].sort((a, b) => a.code.localeCompare(b.code));
  }, [user?.roles]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Manage access definitions and organization master data."
      />

      <div className="grid gap-6 lg:grid-cols-[230px_1fr]">
        <Card className="h-fit p-2">
          <nav className="space-y-1" aria-label="Settings sections">
            {sections.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium ${
                  section === id ? "bg-[#E7F1EE] text-[#086B5A]" : "text-slate-600 hover:bg-slate-50"
                }`}
                onClick={() => setSection(id)}
              >
                <Icon className="h-4 w-4" /> {label}
              </button>
            ))}
          </nav>
        </Card>

        {section === "roles" && (
          <Card>
            <h2 className="text-lg font-semibold">Roles</h2>
            <p className="mt-1 text-sm text-slate-500">
              Role definitions and permission mappings belong in this section.
            </p>
            <div className="mt-5 flex items-center justify-between rounded-lg border p-4">
              <div>
                <div className="font-medium">Visible role definitions</div>
                <div className="text-sm text-slate-500">{user?.roles?.length ?? 0} roles available through your account</div>
              </div>
              <Link className="text-sm font-semibold text-[#086B5A] hover:underline" to="/roles">Review roles</Link>
            </div>
          </Card>
        )}

        {section === "permissions" && (
          <Card>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Permissions</h2>
                <p className="mt-1 text-sm text-slate-500">Permissions granted to the current account.</p>
              </div>
              <Badge variant="warning">Read only</Badge>
            </div>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="border-b text-xs uppercase text-slate-500">
                  <tr><th className="pb-3 font-medium">Code</th><th className="pb-3 font-medium">Description</th><th className="pb-3 font-medium">Module</th></tr>
                </thead>
                <tbody className="divide-y">
                  {permissions.map((permission) => (
                    <tr key={permission.code}>
                      <td className="py-3 font-medium">{permission.code}</td>
                      <td className="py-3 text-slate-600">{permission.description || "—"}</td>
                      <td className="py-3"><Badge variant="outline">{permission.code.split(/[.:_]/)[0] || "General"}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {permissions.length === 0 && <p className="py-10 text-center text-sm text-slate-500">No permissions are visible.</p>}
            </div>
          </Card>
        )}

        {(section === "departments" || section === "locations") && (
          <Card>
            <h2 className="text-lg font-semibold">{section === "departments" ? "Departments" : "Locations"}</h2>
            <div className="mt-5 rounded-lg border border-dashed p-10 text-center">
              <p className="text-sm font-medium">Management API unavailable</p>
              <p className="mt-1 text-xs text-slate-500">
                This backend version does not expose a {section} endpoint, so no unsupported actions are shown.
              </p>
            </div>
          </Card>
        )}

        {section === "warehouses" && (
          <Card>
            <h2 className="text-lg font-semibold">Warehouses</h2>
            <p className="mt-1 text-sm text-slate-500">Create and review warehouse master records.</p>
            <Link
              to="/warehouses"
              className="mt-5 inline-flex rounded-lg bg-[#086B5A] px-4 py-2 text-sm font-semibold text-white hover:bg-[#07594C]"
            >
              Manage Warehouses
            </Link>
          </Card>
        )}
      </div>
    </div>
  );
}

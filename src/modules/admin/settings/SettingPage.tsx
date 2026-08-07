import { KeyRound, ShieldCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";

export default function SettingPage() {
  return <div className="space-y-6">
    <PageHeader title="System Settings" description="System-level access and security settings. Business Units, Departments, Locations and Warehouses remain separate Master Data modules."/>
    <div className="grid gap-4 md:grid-cols-3">
      <Card><ShieldCheck className="mb-3 h-5 w-5 text-emerald-700"/><h2 className="font-semibold">Roles & Permissions</h2><p className="mt-1 text-sm text-slate-500">Manage the HMM-Connect role model and permission mappings.</p><Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/roles">Manage Roles</Link></Card>
      <Card><Users className="mb-3 h-5 w-5 text-emerald-700"/><h2 className="font-semibold">Users</h2><p className="mt-1 text-sm text-slate-500">Create accounts, assign roles and organizational scope, or deactivate access.</p><Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/users">Manage Users</Link></Card>
      <Card><KeyRound className="mb-3 h-5 w-5 text-emerald-700"/><h2 className="font-semibold">Authentication</h2><p className="mt-1 text-sm text-slate-500">Self-registration is disabled. Accounts are provisioned by System Administrators.</p></Card>
    </div>
    <Card className="border-amber-200 bg-amber-50/50"><h2 className="font-semibold">Master Data is managed separately</h2><p className="mt-1 text-sm text-slate-600">Warehouses are physical stock locations. Business Units, Departments and Locations are organization dimensions. They are intentionally not combined with System Settings.</p></Card>
  </div>;
}

import {Building2, KeyRound, Landmark, Network, ShieldCheck, Users, Printer} from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function SettingPage() {
  return <div className="space-y-6">
    <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="System Settings" description="Configure organization, security, approvals, finance policy, and system behavior from one place."/>

    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <Card>
        <ShieldCheck className="mb-3 h-5 w-5 text-emerald-700"/>
        <h2 className="font-semibold">Roles & Permissions</h2>
        <p className="mt-1 text-sm text-slate-500">Manage access roles and permission mappings.</p>
        <Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/roles">Manage Roles</Link>
      </Card>

      <Card>
        <Users className="mb-3 h-5 w-5 text-emerald-700"/>
        <h2 className="font-semibold">Users</h2>
        <p className="mt-1 text-sm text-slate-500">Provision accounts, assign roles, and manage organizational scope.</p>
        <Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/users">Manage Users</Link>
      </Card>

      <Card>
        <Building2 className="mb-3 h-5 w-5 text-emerald-700"/>
        <h2 className="font-semibold">Organization</h2>
        <p className="mt-1 text-sm text-slate-500">Configure Business Units, Departments, Locations, and related organizational dimensions.</p>
        <Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/organization-dimensions">Manage Organization</Link>
      </Card>

      <Card>
        <Network className="mb-3 h-5 w-5 text-emerald-700"/>
        <h2 className="font-semibold">Approval Workflow</h2>
        <p className="mt-1 text-sm text-slate-500">Configure sequential and parallel multi-level approval stages for supported documents.</p>
        <Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/approval-configuration">Configure Approvals</Link>
      </Card>

      <Card>
        <Landmark className="mb-3 h-5 w-5 text-emerald-700"/>
        <h2 className="font-semibold">Finance Setup</h2>
        <p className="mt-1 text-sm text-slate-500">Maintain Chart of Accounts, Posting Rules, and Fiscal Periods outside daily Finance operations.</p>
        <div className="mt-4 flex flex-wrap gap-3 text-sm font-semibold text-emerald-700"><Link className="hover:underline" to="/finance-setup">Finance Setup</Link><Link className="hover:underline" to="/finance-setup/accounting-periods">Periods & Backdate Settings</Link></div>
      </Card>

      <Card>
        <KeyRound className="mb-3 h-5 w-5 text-emerald-700"/>
        <h2 className="font-semibold">Authentication</h2>
        <p className="mt-1 text-sm text-slate-500">Self-registration is disabled. Accounts are provisioned by System Administrators.</p>
        <Link className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline" to="/active-sessions">Manage Active Sessions</Link>
      </Card>
    </div>
  </div>;
}

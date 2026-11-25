import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import DataWorkspace, { WorkspaceFilters } from "@/components/workspace/DataWorkspace";
import SearchableSelect from "@/components/form/SearchableSelect";
import useAuthStore from "@/store/auth";
import { hasPermission } from "@/lib/access";
import { usePosBillingOptions, usePosCateringProfile, usePosOptions, usePosRevenueAccounts } from "../hooks/usePosData";
import OutletSetup from "../OutletSetup";
import OutletCheckoutSettings from "../components/OutletCheckoutSettings";
import HotelOutletSettings from "../components/HotelOutletSettings";
import CateringLocationSetup from "../components/CateringLocationSetup";
import { hotelOutletContext } from "../outletContext";

export default function PosSettingsPage() {
  const user = useAuthStore((state) => state.user);
  const view = hasPermission(user, "pos.view");
  const finance = hasPermission(user, "finance.manage");
  const admin = hasPermission(user, "admin.settings.manage");
  if (!view || (!finance && !admin)) return <p role="alert">You do not have permission to configure POS.</p>;
  return <PosSettings userId={user?.id} finance={finance} admin={admin} />;
}

function PosSettings({ userId, finance, admin }: { userId?: number; finance: boolean; admin: boolean }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [locationId, setLocationId] = useState<number | undefined>(Number(params.get("location")) || undefined);
  const [outletId, setOutletId] = useState<number | undefined>(Number(params.get("outlet")) || undefined);

  const options = usePosOptions(userId);
  const locations = options.data?.locations ?? [];
  const location = locations.find((row) => row.id === locationId);
  const hotel = hotelOutletContext(options.data, locationId, outletId);
  const catering = location?.catalog_type === "CATERING";

  const profile = usePosCateringProfile(userId, locationId, Boolean(catering && finance));
  const billing = usePosBillingOptions(userId, Boolean(catering && finance));
  const revenue = usePosRevenueAccounts(userId, locationId, Boolean(catering && finance));

  const setOutlet = (id?: number) => {
    setOutletId(id);
    setParams({ location: String(locationId), ...(id ? { outlet: String(id) } : {}) }, { replace: true });
  };

  return (
    <DataWorkspace area="Master data">
      <div className="space-y-4">
        <PageHeader
          title="POS Settings"
          description="Hotel outlets, table setup and Catering billing defaults."
          actions={<Link className="text-sm text-emerald-700 underline" to="/settings">System Settings</Link>}
        />
        <WorkspaceFilters label="Location filters" context={location?.name ?? "All sales locations"}>
          <div className="grid gap-3 sm:grid-cols-2">
            <SearchableSelect
              label="Sales location"
              value={location?.id}
              options={locations}
              onChange={(id) => {
                setLocationId(id);
                setOutletId(undefined);
                setParams(id ? { location: String(id) } : {}, { replace: true });
              }}
            />
            {location?.catalog_type === "HOTEL" && (
              <SearchableSelect label="Hotel outlet" value={hotel.department?.id} options={hotel.departments} onChange={setOutlet} />
            )}
          </div>
        </WorkspaceFilters>
        {options.isError && (
          <p role="alert">Sales locations could not load. <button type="button" className="underline" onClick={() => void options.refetch()}>Retry</button></p>
        )}
        {location?.catalog_type === "HOTEL" && (
          <>
            {admin && <OutletSetup key={location.id} userId={userId} locationId={location.id} canManage={admin} onSaved={setOutlet} />}
            {hotel.valid && finance && (
              <>
                <HotelOutletSettings key={`${location.id}:${outletId}`} userId={userId} locationId={location.id} departmentId={hotel.department!.id} />
                <OutletCheckoutSettings key={`checkout:${location.id}:${outletId}`} userId={userId} locationId={location.id} departmentId={hotel.department!.id} />
              </>
            )}
            {!finance && <p className="text-sm text-slate-600">Order mode and table settings require Finance management permission.</p>}
            {hotel.valid && <Link className="inline-block text-sm text-emerald-700 underline" to={hotel.href}>Open outlet operations</Link>}
            {!hotel.valid && <p className="text-sm text-slate-600">Select a Food &amp; Beverage outlet, or configure one above.</p>}
          </>
        )}
        {catering && (!finance ? (
          <p className="text-sm text-slate-600">Catering billing defaults require Finance management permission.</p>
        ) : profile.isLoading ? (
          <p>Loading Catering settings…</p>
        ) : profile.isError || billing.isError || revenue.isError ? (
          <p role="alert">Catering settings could not load. Refresh and check access.</p>
        ) : profile.data ? (
          <CateringLocationSetup
            key={location.id}
            locationId={location.id}
            profile={profile.data}
            customers={billing.data?.customers ?? []}
            departments={(options.data?.departments ?? []).filter((row) => row.location_id === location.id)}
            revenueAccounts={revenue.data ?? []}
            receivableAccounts={billing.data?.receivable_accounts ?? []}
            onClose={() => navigate("/settings")}
            onSaved={() => {
              void client.invalidateQueries({ queryKey: ["catering-billing"] });
              void client.invalidateQueries({ queryKey: ["pos-products"] });
            }}
          />
        ) : null)}
        {!location && !options.isLoading && !options.isError && (
          <p className="text-sm text-slate-500">Choose a sales location to configure POS.</p>
        )}
      </div>
    </DataWorkspace>
  );
}

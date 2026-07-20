import { useState } from "react";
import { MapPin, Pencil, Plus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { getLocations, createLocation, updateLocation, type Location } from "../features/locations/locationsApi";

export default function LocationsPage() {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const locationsQuery = useQuery({ queryKey: ["locations"], queryFn: getLocations });

  return <div className="space-y-6"><PageHeader title="Locations" description="Define the operational context captured in the audit trail." actions={<Button onClick={() => { setEditing(null); setOpen(true); }}><Plus size={18} /> Add location</Button>} /><div className="rounded-xl border border-slate-200 bg-white"><div className="border-b border-slate-200 p-6"><h2 className="font-semibold text-slate-900">Locations</h2></div>{locationsQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading locations...</div>}{!locationsQuery.isLoading && !locationsQuery.data?.length && <EmptyState title="No locations found" description="Create a location for audit context." action={<Button onClick={() => setOpen(true)}><Plus size={18} /> Add location</Button>} />}{!!locationsQuery.data?.length && <div className="divide-y divide-slate-100">{locationsQuery.data.map((location) => <div key={location.id} className="flex items-center justify-between p-5"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100"><MapPin size={18} className="text-slate-600" /></div><div><p className="font-medium text-slate-900">{location.code} · {location.name}</p><p className="mt-1 text-sm text-slate-500">{location.location_type}</p></div></div><Button variant="ghost" onClick={() => { setEditing(location); setOpen(true); }}><Pencil size={16} /> Edit</Button></div>)}</div>}</div><LocationModal key={editing?.id ?? "new"} open={open} location={editing} onClose={() => setOpen(false)} /></div>;
}

function LocationModal({ open, location, onClose }: { open: boolean; location: Location | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState(location?.code ?? "");
  const [name, setName] = useState(location?.name ?? "");
  const [type, setType] = useState(location?.location_type ?? "OFFICE");

  const mutation = useMutation({
    mutationFn: () => location ? updateLocation(location.id, { name, location_type: type }) : createLocation({ code, name, location_type: type }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["locations"] }); onClose(); },
  });

  return <Modal open={open} onClose={onClose} title={location ? "Edit location" : "Create location"} description="A user's location is captured in every new audit event." footer={<><Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>Cancel</Button><Button type="button" onClick={() => mutation.mutate()} loading={mutation.isPending}>{location ? "Save changes" : "Create location"}</Button></>}><div className="space-y-4">{!location && <Input label="Code" value={code} onChange={(event) => setCode(event.target.value)} placeholder="JKT" />}<Input label="Name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Jakarta Office" /><Input label="Type" value={type} onChange={(event) => setType(event.target.value)} placeholder="OFFICE" />{mutation.isError && <p className="text-sm text-red-600">Failed to save location.</p>}</div></Modal>;
}

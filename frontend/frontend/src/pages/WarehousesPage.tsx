import { useState } from "react";
import { Plus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import { createWarehouse, getWarehouses } from "../features/warehouses/warehousesApi";

export default function WarehousesPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");

  const warehousesQuery = useQuery({ queryKey: ["warehouses"], queryFn: getWarehouses });
  const createMutation = useMutation({
    mutationFn: createWarehouse,
    onSuccess: () => {
      resetForm();
      queryClient.invalidateQueries({ queryKey: ["warehouses"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const warehouses = warehousesQuery.data ?? [];

  function resetForm() {
    setOpen(false);
    setCode("");
    setName("");
    setAddress("");
    createMutation.reset();
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!code.trim() || !name.trim()) return;
    createMutation.mutate({ code: code.trim(), name: name.trim(), address: address.trim() || undefined });
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Warehouses" description="Manage stock locations used by inventory receipts." actions={<Button type="button" onClick={() => { createMutation.reset(); setOpen(true); }}><Plus size={16} className="mr-2" />Add warehouse</Button>} />

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-6"><div><h2 className="font-semibold text-slate-900">Warehouses</h2><p className="mt-1 text-sm text-slate-500">{warehouses.length} locations</p></div></div>
        {warehousesQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading warehouses...</div>}
        {warehousesQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load warehouses.</div>}
        {!warehousesQuery.isLoading && !warehousesQuery.isError && warehouses.length === 0 && <EmptyState title="No warehouses yet" description="Add a warehouse before receiving stock into inventory." action={<Button type="button" onClick={() => setOpen(true)}><Plus size={16} className="mr-2" />Add warehouse</Button>} />}
        {warehouses.length > 0 && <div className="overflow-x-auto"><table className="w-full min-w-[700px]"><thead><tr className="border-b border-slate-200 text-left"><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Code</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Name</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Address</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th></tr></thead><tbody>{warehouses.map((warehouse) => <tr key={warehouse.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50"><td className="px-6 py-4 font-mono text-sm font-medium text-slate-900">{warehouse.code}</td><td className="px-6 py-4 text-sm text-slate-700">{warehouse.name}</td><td className="px-6 py-4 text-sm text-slate-600">{warehouse.address ?? "—"}</td><td className="px-6 py-4"><StatusBadge status={warehouse.is_active ? "ACTIVE" : "INACTIVE"} /></td></tr>)}</tbody></table></div>}
      </div>

      <Modal open={open} onClose={resetForm} title="Add warehouse" description="Create a stock location for inventory receipts." size="sm" closeDisabled={createMutation.isPending} footer={<><Button type="button" variant="secondary" onClick={resetForm} disabled={createMutation.isPending}>Cancel</Button><Button type="submit" form="create-warehouse-form" loading={createMutation.isPending}>Create warehouse</Button></>}>
        <form id="create-warehouse-form" onSubmit={handleSubmit} className="space-y-4"><div><label className="mb-2 block text-sm font-medium text-slate-700">Code</label><input value={code} onChange={(event) => setCode(event.target.value)} placeholder="WH-JKT" className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" required /></div><div><label className="mb-2 block text-sm font-medium text-slate-700">Name</label><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Jakarta Warehouse" className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" required /></div><div><label className="mb-2 block text-sm font-medium text-slate-700">Address</label><textarea value={address} onChange={(event) => setAddress(event.target.value)} rows={3} placeholder="Optional" className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" /></div>{createMutation.isError && <p className="text-sm text-red-600">Failed to create warehouse.</p>}</form>
      </Modal>
    </div>
  );
}

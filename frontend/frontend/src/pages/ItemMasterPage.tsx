import { useState } from "react";
import { Plus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../api/client";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";

interface Item {
  id: number;
  code: string;
  name: string;
  group_code: string;
  group_name: string;
  subgroup_code: string;
  subgroup_name: string;
  uom: string;
  usage_uom: string;
  conversion: number;
  is_active: boolean;
}

interface ItemGroup {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

interface ItemSubgroup {
  id: number;
  code: string;
  name: string;
  group_id: number;
  is_active: boolean;
}

interface Inventory {
  product_id: number;
  code: string;
  name: string;
  uom: string;
  quantity: number;
  average_cost: number;
}

const uoms = ["Kg", "Gram", "Liter", "Ml", "Pcs", "Box", "Bottle", "Pack"];
const usageUoms = ["Kg", "Gram", "Liter", "Ml", "Pcs"];

async function getItems(): Promise<Item[]> {
  const response = await api.get<Item[]>("/products");
  return response.data;
}

async function getGroups(): Promise<ItemGroup[]> {
  const response = await api.get<ItemGroup[]>("/item-classification/groups");
  return response.data;
}

async function getSubgroups(groupId: number): Promise<ItemSubgroup[]> {
  const response = await api.get<ItemSubgroup[]>("/item-classification/subgroups", { params: { group_id: groupId } });
  return response.data;
}

async function getInventory(): Promise<Inventory[]> {
  const response = await api.get<Inventory[]>("/inventory");
  return response.data;
}

async function createItem(data: { name: string; group_code: string; group_name: string; subgroup_code: string; subgroup_name: string; uom: string; usage_uom: string; conversion: number }) {
  const response = await api.post("/products", data);
  return response.data;
}

export default function ItemMasterPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [groupId, setGroupId] = useState("");
  const [subgroupId, setSubgroupId] = useState("");
  const [uom, setUom] = useState("");
  const [usageUom, setUsageUom] = useState("");
  const [conversion, setConversion] = useState("1");

  const itemsQuery = useQuery({ queryKey: ["items"], queryFn: getItems });
  const groupsQuery = useQuery({ queryKey: ["item-groups"], queryFn: getGroups });
  const subgroupsQuery = useQuery({ queryKey: ["item-subgroups", groupId], queryFn: () => getSubgroups(Number(groupId)), enabled: Boolean(groupId) });
  const inventoryQuery = useQuery({ queryKey: ["inventory"], queryFn: getInventory });

  const createMutation = useMutation({
    mutationFn: createItem,
    onSuccess: () => {
      resetForm();
      queryClient.invalidateQueries({ queryKey: ["items"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const items = itemsQuery.data ?? [];
  const groups = groupsQuery.data ?? [];
  const subgroups = subgroupsQuery.data ?? [];
  const inventory = inventoryQuery.data ?? [];
  const selectedGroup = groups.find((group) => group.id === Number(groupId));
  const selectedSubgroup = subgroups.find((subgroup) => subgroup.id === Number(subgroupId));

  function resetForm() {
    setCreateOpen(false);
    setName("");
    setGroupId("");
    setSubgroupId("");
    setUom("");
    setUsageUom("");
    setConversion("1");
    createMutation.reset();
  }

  function getStock(productId: number) {
    return inventory.find((stock) => stock.product_id === productId);
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !selectedGroup || !selectedSubgroup || !uom || !usageUom || Number(conversion) <= 0) return;

    createMutation.mutate({
      name: name.trim(),
      group_code: selectedGroup.code,
      group_name: selectedGroup.name,
      subgroup_code: selectedSubgroup.code,
      subgroup_name: selectedSubgroup.name,
      uom,
      usage_uom: usageUom,
      conversion: Number(conversion),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Item Master" description="Manage items, classifications, units, and conversion rules." actions={<Button type="button" onClick={() => { createMutation.reset(); setCreateOpen(true); }}><Plus size={16} className="mr-2" />Create item</Button>} />

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-6"><div><h2 className="font-semibold text-slate-900">Items</h2><p className="mt-1 text-sm text-slate-500">{items.length} items</p></div></div>
        {itemsQuery.isLoading && <div className="p-8 text-center text-sm text-slate-500">Loading items...</div>}
        {itemsQuery.isError && <div className="p-8 text-center text-sm text-red-600">Failed to load items.</div>}
        {!itemsQuery.isLoading && !itemsQuery.isError && items.length === 0 && <EmptyState title="No items yet" description="Create your first item and classify it by group and subgroup." action={<Button type="button" onClick={() => setCreateOpen(true)}><Plus size={16} className="mr-2" />Create item</Button>} />}
        {items.length > 0 && <div className="overflow-x-auto"><table className="w-full min-w-[1000px]"><thead><tr className="border-b border-slate-200 text-left"><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Code</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Item</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Group</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Subgroup</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">UOM</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Usage</th><th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Stock</th><th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Convert</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50"><td className="px-6 py-4 font-mono text-sm font-medium text-slate-900">{item.code}</td><td className="px-6 py-4 text-sm text-slate-700">{item.name}</td><td className="px-6 py-4 text-sm text-slate-600">{item.group_name}</td><td className="px-6 py-4 text-sm text-slate-600">{item.subgroup_name}</td><td className="px-6 py-4 text-sm text-slate-600">{item.uom}</td><td className="px-6 py-4 text-sm text-slate-600">{item.usage_uom}</td><td className="px-6 py-4 text-right text-sm font-medium text-slate-900">{getStock(item.id)?.quantity ?? 0} {item.uom}</td><td className="px-6 py-4 text-right text-sm text-slate-600">{item.conversion}</td></tr>)}</tbody></table></div>}
      </div>

      <Modal open={createOpen} onClose={resetForm} title="Create item" description="Add a new item to the item master." size="lg" closeDisabled={createMutation.isPending} footer={<><Button type="button" variant="secondary" onClick={resetForm} disabled={createMutation.isPending}>Cancel</Button><Button type="submit" form="create-item-form" loading={createMutation.isPending} disabled={groupsQuery.isLoading || subgroupsQuery.isLoading}>Create item</Button></>}>
        <form id="create-item-form" onSubmit={handleSubmit} className="space-y-5">
          <div><label className="mb-2 block text-sm font-medium text-slate-700">Item name</label><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Daging Khas Dalam" className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" required /></div>
          <div className="grid gap-4 sm:grid-cols-2"><div><label className="mb-2 block text-sm font-medium text-slate-700">Group</label><Select value={groupId} onChange={(value) => { setGroupId(value); setSubgroupId(""); }} placeholder="Select group" options={groups.map((group) => ({ value: String(group.id), label: `${group.code} - ${group.name}` }))} />{groupsQuery.isLoading && <p className="mt-1 text-xs text-slate-500">Loading groups...</p>}{groupsQuery.isError && <p className="mt-1 text-xs text-red-600">Failed to load groups.</p>}</div><div><label className="mb-2 block text-sm font-medium text-slate-700">Subgroup</label><Select value={subgroupId} onChange={setSubgroupId} placeholder={groupId ? "Select subgroup" : "Select group first"} disabled={!groupId} options={subgroups.map((subgroup) => ({ value: String(subgroup.id), label: `${subgroup.code} - ${subgroup.name}` }))} />{groupId && subgroupsQuery.isLoading && <p className="mt-1 text-xs text-slate-500">Loading subgroups...</p>}{subgroupsQuery.isError && <p className="mt-1 text-xs text-red-600">Failed to load subgroups.</p>}</div></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">Item code is generated automatically.</p><p className="mt-1 font-mono text-sm font-semibold text-slate-900">{selectedGroup?.code || "X"}-100001</p></div>
          <div className="grid gap-4 sm:grid-cols-2"><div><label className="mb-2 block text-sm font-medium text-slate-700">UOM</label><Select value={uom} onChange={setUom} placeholder="Select UOM" options={uoms.map((value) => ({ value, label: value }))} /></div><div><label className="mb-2 block text-sm font-medium text-slate-700">Usage UOM</label><Select value={usageUom} onChange={setUsageUom} placeholder="Select usage UOM" options={usageUoms.map((value) => ({ value, label: value }))} /></div></div>
          <div><label className="mb-2 block text-sm font-medium text-slate-700">Conversion</label><input type="number" min="0.0001" step="0.0001" value={conversion} onChange={(event) => setConversion(event.target.value)} className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10" required /><p className="mt-1 text-xs text-slate-500">Example: 1 box = 12 pcs.</p></div>
          {createMutation.isError && <p className="text-sm text-red-600">Failed to create item.</p>}
        </form>
      </Modal>
    </div>
  );
}

import { useMemo, useState, type FormEvent } from "react";
import axios from "axios";
import { Search, Warehouse as WarehouseIcon } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import { useCreateWarehouse, useWarehouses } from "./hooks/useWarehouses";
import type { Warehouse } from "./types";

type StatusFilter = "ALL" | "ACTIVE" | "INACTIVE";

function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Unable to save the warehouse.";
  const data = error.response?.data as { detail?: string } | undefined;
  if (typeof data?.detail === "string") return data.detail;
  if (error.response?.status === 403) return "You do not have permission to manage warehouses.";
  if (error.response?.status === 409) return "A warehouse with this code already exists.";
  if (error.response?.status === 422) return "Please check the warehouse fields.";
  return "Unable to save the warehouse.";
}

export default function WarehousePage() {
  const warehouses = useWarehouses();
  const createWarehouse = useCreateWarehouse();
  const [showForm, setShowForm] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [formError, setFormError] = useState("");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (warehouses.data ?? []).filter((warehouse: Warehouse) => {
      const matchesStatus =
        status === "ALL" ||
        (status === "ACTIVE" ? warehouse.is_active : !warehouse.is_active);
      const matchesSearch =
        !term ||
        [warehouse.code, warehouse.name, warehouse.address]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(term);
      return matchesStatus && matchesSearch;
    });
  }, [search, status, warehouses.data]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (createWarehouse.isPending) return;
    if (!code.trim() || !name.trim()) {
      setFormError("Code and warehouse name are required.");
      return;
    }
    setFormError("");
    try {
      await createWarehouse.mutateAsync({
        code: code.trim(),
        name: name.trim(),
        address: address.trim() || null,
      });
      toast.success("Warehouse created successfully.");
      setCode("");
      setName("");
      setAddress("");
      setShowForm(false);
    } catch (error) {
      setFormError(errorMessage(error));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Warehouses"
        description="Manage warehouse master records used for receiving and inventory."
        actions={
          <Button onClick={() => {
            setShowForm((value) => !value);
            setFormError("");
          }}>
            {showForm ? "Close" : "Add Warehouse"}
          </Button>
        }
      />

      {showForm && (
        <Card>
          <form className="grid gap-4 md:grid-cols-4" onSubmit={submit}>
            {formError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 md:col-span-4">
                {formError}
              </div>
            )}
            <Input required placeholder="Code" value={code} disabled={createWarehouse.isPending} onChange={(event) => setCode(event.target.value)} />
            <Input required placeholder="Warehouse name" value={name} disabled={createWarehouse.isPending} onChange={(event) => setName(event.target.value)} />
            <Input placeholder="Address" value={address} disabled={createWarehouse.isPending} onChange={(event) => setAddress(event.target.value)} />
            <Button type="submit" loading={createWarehouse.isPending}>Save Warehouse</Button>
          </form>
        </Card>
      )}

      <Card>
        <div className="mb-5 flex flex-col gap-3 sm:flex-row">
          <div className="relative w-full sm:max-w-md">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input type="search" placeholder="Search warehouses..." value={search} className="pl-9" onChange={(event) => setSearch(event.target.value)} />
          </div>
          <select
            value={status}
            aria-label="Filter warehouses by status"
            className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
            onChange={(event) => setStatus(event.target.value as StatusFilter)}
          >
            <option value="ALL">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </select>
        </div>

        {warehouses.isLoading ? (
          <div className="py-12"><Loading /></div>
        ) : warehouses.isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-sm text-red-700">Warehouses could not be loaded.</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => warehouses.refetch()}>Try Again</Button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center">
            <WarehouseIcon className="mx-auto mb-2 h-8 w-8 text-slate-400" />
            <p className="text-sm font-medium">No warehouses match the filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="border-b text-xs uppercase text-slate-500">
                <tr>
                  <th className="pb-3 font-medium">Code</th>
                  <th className="pb-3 font-medium">Name</th>
                  <th className="pb-3 font-medium">Address</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filtered.map((warehouse) => (
                  <tr key={warehouse.id}>
                    <td className="py-4 font-semibold">{warehouse.code}</td>
                    <td className="py-4">{warehouse.name}</td>
                    <td className="py-4">{warehouse.address ?? "—"}</td>
                    <td className="py-4">
                      <Badge variant={warehouse.is_active ? "success" : "secondary"}>
                        {warehouse.is_active ? "Active" : "Inactive"}
                      </Badge>
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

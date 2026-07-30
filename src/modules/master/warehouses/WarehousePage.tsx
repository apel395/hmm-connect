import { useState } from "react";

import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";

import { useCreateWarehouse, useWarehouses } from "./hooks/useWarehouses";
import type { Warehouse } from "./types";

export default function WarehousePage() {
  const { data: warehouses = [], isLoading } = useWarehouses();
  const createWarehouse = useCreateWarehouse();
  const [showForm, setShowForm] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    await createWarehouse.mutateAsync({
      code,
      name,
      address: address || null,
    });
    setCode("");
    setName("");
    setAddress("");
    setShowForm(false);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Warehouses"
        description="Warehouse master records used for receiving and inventory."
        actions={
          <Button onClick={() => setShowForm((value) => !value)}>
            {showForm ? "Close" : "New Warehouse"}
          </Button>
        }
      />

      {showForm && (
        <Card className="p-5">
          <form
            className="grid gap-4 md:grid-cols-4"
            onSubmit={submit}
          >
            <Input
              required
              placeholder="Code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
            <Input
              required
              placeholder="Warehouse name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Input
              placeholder="Address"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
            />
            <Button type="submit" loading={createWarehouse.isPending}>
              Save Warehouse
            </Button>
          </form>
        </Card>
      )}

      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-12"><Loading /></div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left">Code</th>
                <th className="px-5 py-3 text-left">Name</th>
                <th className="px-5 py-3 text-left">Address</th>
                <th className="px-5 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {warehouses.map((warehouse: Warehouse) => (
                <tr key={warehouse.id} className="border-t">
                  <td className="px-5 py-3 font-medium">{warehouse.code}</td>
                  <td className="px-5 py-3">{warehouse.name}</td>
                  <td className="px-5 py-3">{warehouse.address ?? "-"}</td>
                  <td className="px-5 py-3">
                    {warehouse.is_active ? "Active" : "Inactive"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
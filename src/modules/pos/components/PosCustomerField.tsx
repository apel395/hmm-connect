import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import { posApi } from "../api";

type Customer = { id: number; code: string; name: string };

export default function PosCustomerField({ value, onChange, customers = [], canCreate = false }: {
  value?: number;
  onChange: (value: number | undefined) => void;
  customers?: Customer[];
  canCreate?: boolean;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const create = useMutation({
    mutationFn: async () => (await posApi.createCustomer({ customer_name: name.trim(), phone: phone.trim() || undefined })).data as Customer,
    onSuccess: (customer) => {
      queryClient.setQueriesData({ queryKey: ["pos-billing-options"] }, (previous: any) => previous ? {
        ...previous,
        customers: [...(previous.customers ?? []).filter((row: Customer) => row.id !== customer.id), customer].sort((a: Customer, b: Customer) => a.name.localeCompare(b.name)),
      } : previous);
      void queryClient.invalidateQueries({ queryKey: ["pos-billing-options"] });
      onChange(customer.id);
      setOpen(false);
      setName("");
      setPhone("");
      setError("");
    },
    onError: (reason: any) => setError(typeof reason?.response?.data?.detail === "string" ? reason.response.data.detail : "Could not create customer"),
  });
  return <>
    <div className="space-y-1">
      <SearchableSelect label="Customer" required value={value} options={customers} placeholder="Type customer code or name..." onChange={onChange} />
      {canCreate && <Button size="sm" variant="outline" onClick={() => { setError(""); setOpen(true); }}><Plus size={14}/> Add customer</Button>}
      {customers.length === 0 && <p className="text-xs text-amber-700">No customers available. Add a customer before posting an invoice.</p>}
    </div>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Add customer</DialogTitle></DialogHeader>
        <DialogBody className="space-y-3">
          <label className="block text-sm">Customer name *<input className="mt-1 h-10 w-full rounded border px-3" value={name} maxLength={200} onChange={event => setName(event.target.value)} placeholder="Customer name" /></label>
          <label className="block text-sm">Phone (optional)<input className="mt-1 h-10 w-full rounded border px-3" value={phone} maxLength={50} onChange={event => setPhone(event.target.value)} /></label>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        </DialogBody>
        <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>Save customer</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}

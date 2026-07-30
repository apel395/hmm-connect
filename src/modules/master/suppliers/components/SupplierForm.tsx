import { useEffect, useState, type FormEvent } from "react";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import type { Supplier, SupplierPayload, SupplierPICPayload } from "../types";

interface Props {
  open: boolean;
  supplier?: Supplier | null;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (payload: SupplierPayload) => void;
}

const emptyForm: SupplierPayload = {
  code: "",
  name: "",
  address: "",
  bank_name: "",
  bank_account_number: "",
  bank_account_name: "",
  is_active: true,
  rows: [],
};

const emptyPic = (): SupplierPICPayload => ({
  pic_name: "",
  phone: null,
  unit: null,
  item: null,
});

export default function SupplierForm({
  open,
  supplier,
  loading = false,
  error,
  onClose,
  onSubmit,
}: Props) {
  const [form, setForm] = useState<SupplierPayload>(emptyForm);
  const [validation, setValidation] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setValidation(null);
    setForm(
      supplier
        ? {
            code: supplier.code,
            name: supplier.name,
            address: supplier.address ?? "",
            bank_name: supplier.bank_name ?? "",
            bank_account_number: supplier.bank_account_number ?? "",
            bank_account_name: supplier.bank_account_name ?? "",
            is_active: supplier.is_active,
            rows: supplier.rows?.map((row) => ({
              id: row.id,
              pic_name: row.pic_name,
              phone: row.phone,
              unit: row.unit,
              item: row.item,
            })) ?? [],
          }
        : { ...emptyForm, rows: [emptyPic()] }
    );
  }, [open, supplier]);

  function setField<K extends keyof Omit<SupplierPayload, "rows">>(
    field: K,
    value: SupplierPayload[K]
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updatePic(
    index: number,
    field: keyof Omit<SupplierPICPayload, "id">,
    value: string
  ) {
    setForm((current) => ({
      ...current,
      rows: current.rows.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [field]: value } : row
      ),
    }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    const code = form.code.trim();
    const name = form.name.trim();
    if (!code || !name) {
      setValidation("Supplier code and supplier name are required.");
      return;
    }
    setValidation(null);
    const trim = (value: string | null) => value?.trim() || null;
    onSubmit({
      ...form,
      code,
      name,
      address: form.address.trim(),
      bank_name: form.bank_name.trim(),
      bank_account_number: form.bank_account_number.trim(),
      bank_account_name: form.bank_account_name.trim(),
      rows: form.rows
        .map((row) => ({
          ...row,
          pic_name: row.pic_name.trim(),
          phone: trim(row.phone),
          unit: trim(row.unit),
          item: trim(row.item),
        }))
        .filter((row) => row.pic_name),
    });
  }

  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{supplier ? "Edit Supplier" : "Add Supplier"}</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <div className="space-y-6">
              {(validation || error) && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {validation || error}
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-sm font-medium">
                  <span>Supplier Code *</span>
                  <Input
                    value={form.code}
                    error={!!validation && !form.code.trim()}
                    disabled={loading}
                    onChange={(event) => setField("code", event.target.value)}
                  />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Supplier Name *</span>
                  <Input
                    value={form.name}
                    error={!!validation && !form.name.trim()}
                    disabled={loading}
                    onChange={(event) => setField("name", event.target.value)}
                  />
                </label>
                <label className="space-y-1 text-sm font-medium sm:col-span-2">
                  <span>Address</span>
                  <Input
                    value={form.address}
                    disabled={loading}
                    onChange={(event) => setField("address", event.target.value)}
                  />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Bank Name</span>
                  <Input
                    value={form.bank_name}
                    disabled={loading}
                    onChange={(event) => setField("bank_name", event.target.value)}
                  />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Account Number</span>
                  <Input
                    value={form.bank_account_number}
                    disabled={loading}
                    onChange={(event) =>
                      setField("bank_account_number", event.target.value)
                    }
                  />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>Account Name</span>
                  <Input
                    value={form.bank_account_name}
                    disabled={loading}
                    onChange={(event) =>
                      setField("bank_account_name", event.target.value)
                    }
                  />
                </label>
                <label className="flex items-center gap-2 pt-6 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    disabled={loading}
                    onChange={(event) => setField("is_active", event.target.checked)}
                  />
                  Active supplier
                </label>
              </div>

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">Contact Persons</h3>
                    <p className="text-sm text-slate-500">
                      Add the people responsible for this supplier.
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={loading}
                    onClick={() =>
                      setForm((current) => ({
                        ...current,
                        rows: [...current.rows, emptyPic()],
                      }))
                    }
                  >
                    Add Contact
                  </Button>
                </div>
                <div className="space-y-3">
                  {form.rows.map((row, index) => (
                    <div
                      key={row.id ?? index}
                      className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-2 lg:grid-cols-5"
                    >
                      <Input
                        aria-label="Contact person"
                        placeholder="Contact person"
                        value={row.pic_name}
                        disabled={loading}
                        onChange={(event) =>
                          updatePic(index, "pic_name", event.target.value)
                        }
                      />
                      <Input
                        aria-label="Phone"
                        placeholder="Phone"
                        value={row.phone ?? ""}
                        disabled={loading}
                        onChange={(event) =>
                          updatePic(index, "phone", event.target.value)
                        }
                      />
                      <Input
                        aria-label="Department"
                        placeholder="Department"
                        value={row.unit ?? ""}
                        disabled={loading}
                        onChange={(event) =>
                          updatePic(index, "unit", event.target.value)
                        }
                      />
                      <Input
                        aria-label="Items"
                        placeholder="Items"
                        value={row.item ?? ""}
                        disabled={loading}
                        onChange={(event) =>
                          updatePic(index, "item", event.target.value)
                        }
                      />
                      <Button
                        type="button"
                        variant="outline"
                        disabled={loading}
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            rows: current.rows.filter((_, i) => i !== index),
                          }))
                        }
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={loading} onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              {supplier ? "Save Changes" : "Create Supplier"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

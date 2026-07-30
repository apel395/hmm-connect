import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import type { Supplier } from "../types";

interface Props {
  open: boolean;
  supplier?: Supplier;
  loading: boolean;
  error?: string | null;
  onClose: () => void;
}

export default function SupplierDetail({
  open,
  supplier,
  loading,
  error,
  onClose,
}: Props) {
  const availableFields: Array<[string, string | null | undefined]> = supplier
    ? [
        ["Supplier Code", supplier.code],
        ["Supplier Name", supplier.name],
        ["Address", supplier.address],
        ["Bank Name", supplier.bank_name],
        ["Account Number", supplier.bank_account_number],
        ["Account Name", supplier.bank_account_name],
        ["Created", supplier.created_at && new Date(supplier.created_at).toLocaleString()],
        ["Updated", supplier.updated_at && new Date(supplier.updated_at).toLocaleString()],
      ]
    : [];
  const fields = availableFields.filter(
    (field): field is [string, string] => Boolean(field[1])
  );

  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Supplier Details</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {loading ? (
            <Loading />
          ) : error ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
              {error}
            </div>
          ) : supplier ? (
            <div className="space-y-6">
              <Badge variant={supplier.is_active ? "success" : "secondary"}>
                {supplier.is_active ? "Active" : "Inactive"}
              </Badge>
              <dl className="grid gap-4 sm:grid-cols-2">
                {fields.map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {label}
                    </dt>
                    <dd className="mt-1 whitespace-pre-wrap text-sm text-slate-900">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
              {(supplier.rows?.length ?? 0) > 0 && (
                <div>
                  <h3 className="mb-3 font-semibold">Contact Persons</h3>
                  <div className="space-y-2">
                    {(supplier.rows ?? []).map((contact) => (
                      <div key={contact.id} className="rounded-lg border border-slate-200 p-3">
                        <div className="font-medium">{contact.pic_name}</div>
                        {[contact.phone, contact.unit, contact.item].filter(Boolean).join(" • ")}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

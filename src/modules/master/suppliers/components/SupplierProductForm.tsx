import { useEffect, useState } from "react";

import Dialog, {
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/Dialog";

import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";

import { useProducts } from "@/modules/master/products/hooks/useProducts";

interface Props {
  open: boolean;

  loading?: boolean;

  onClose: () => void;

  onSubmit: (payload: any) => void;
}

export default function SupplierProductForm({
  open,
  loading,
  onClose,
  onSubmit,
}: Props) {
  const { data: products = [] } =
    useProducts();

  const [form, setForm] =
    useState({
      product_id: "",

      last_price: 0,

      lead_time: 1,

      preferred: true,
    });

  useEffect(() => {
    if (!open) return;

    setForm({
      product_id: "",

      last_price: 0,

      lead_time: 1,

      preferred: true,
    });
  }, [open]);

  function save() {
    onSubmit({
      product_id: Number(
        form.product_id
      ),

      last_price: Number(
        form.last_price
      ),

      lead_time: Number(
        form.lead_time
      ),

      preferred:
        form.preferred,
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent className="max-w-lg">

        <DialogHeader>
          <DialogTitle>
            Assign Product
          </DialogTitle>
        </DialogHeader>

        <DialogBody>

          <div className="space-y-4">

            <div>
              <label className="mb-1 block text-sm font-medium">
                Product
              </label>

              <select
                className="h-10 w-full rounded-md border border-slate-300 px-3"
                value={
                  form.product_id
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    product_id:
                      e.target.value,
                  })
                }
              >
                <option value="">
                  Select Product
                </option>

                {products.map(
                  (p: any) => (
                    <option
                      key={p.id}
                      value={p.id}
                    >
                      {p.code} -{" "}
                      {p.name}
                    </option>
                  )
                )}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Last Purchase Price
              </label>

              <Input
                type="number"
                value={
                  form.last_price
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    last_price:
                      Number(
                        e.target.value
                      ),
                  })
                }
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Lead Time (Days)
              </label>

              <Input
                type="number"
                value={
                  form.lead_time
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    lead_time:
                      Number(
                        e.target.value
                      ),
                  })
                }
              />
            </div>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={
                  form.preferred
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    preferred:
                      e.target
                        .checked,
                  })
                }
              />

              Preferred Supplier
            </label>

          </div>

        </DialogBody>

        <DialogFooter>

          <Button
            variant="outline"
            onClick={onClose}
          >
            Cancel
          </Button>

          <Button
            loading={loading}
            onClick={save}
          >
            Save
          </Button>

        </DialogFooter>

      </DialogContent>
    </Dialog>
  );
}

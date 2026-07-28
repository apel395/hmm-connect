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

import type { Supplier } from "../types";

interface PICRow {
  id?: number;

  pic_name: string;

  phone: string;

  unit: string;

  item: string;
}

interface Props {
  open: boolean;

  supplier?: Supplier | null;

  loading?: boolean;

  onClose: () => void;

  onSubmit: (payload: any) => void;
}

export default function SupplierForm({
  open,
  supplier,
  loading,
  onClose,
  onSubmit,
}: Props) {
  const isEdit = !!supplier;

  const [form, setForm] = useState({
    code: "",

    name: "",

    address: "",

    bank_name: "",

    bank_account_number: "",

    bank_account_name: "",

    is_active: true,
  });

  const [rows, setRows] = useState<PICRow[]>([
    {
      pic_name: "",

      phone: "",

      unit: "",

      item: "",
    },
  ]);

  useEffect(() => {
    if (!open) return;

    if (!supplier) {
      setForm({
        code: "",

        name: "",

        address: "",

        bank_name: "",

        bank_account_number: "",

        bank_account_name: "",

        is_active: true,
      });

      setRows([
        {
          pic_name: "",

          phone: "",

          unit: "",

          item: "",
        },
      ]);

      return;
    }

    setForm({
      code: supplier.code,

      name: supplier.name,

      address: supplier.address,

      bank_name: supplier.bank_name,

      bank_account_number:
        supplier.bank_account_number,

      bank_account_name:
        supplier.bank_account_name,

      is_active: supplier.is_active,
    });

    setRows(
      supplier.rows.length
        ? supplier.rows.map((r) => ({
            id: r.id,

            pic_name: r.pic_name,

            phone: r.phone ?? "",

            unit: r.unit ?? "",

            item: r.item ?? "",
          }))
        : [
            {
              pic_name: "",

              phone: "",

              unit: "",

              item: "",
            },
          ]
    );
  }, [open, supplier]);

  function updateRow(
    index: number,
    field: keyof PICRow,
    value: string
  ) {
    const next = [...rows];

    next[index] = {
      ...next[index],
      [field]: value,
    };

    setRows(next);
  }

  function addRow() {
    setRows([
      ...rows,
      {
        pic_name: "",

        phone: "",

        unit: "",

        item: "",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows(
      rows.filter((_, i) => i !== index)
    );
  }

  function save() {
    onSubmit({
      ...form,

      rows,
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) {
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit
              ? "Edit Supplier"
              : "New Supplier"}
          </DialogTitle>
        </DialogHeader>

        <DialogBody>

          <div className="space-y-6">

            <div className="grid grid-cols-2 gap-4">

              <Input
                placeholder="Supplier Code"
                value={form.code}
                onChange={(e) =>
                  setForm({
                    ...form,
                    code: e.target.value,
                  })
                }
              />

              <Input
                placeholder="Supplier Name"
                value={form.name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    name: e.target.value,
                  })
                }
              />

              <div className="col-span-2">
                <Input
                  placeholder="Address"
                  value={form.address}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      address:
                        e.target.value,
                    })
                  }
                />
              </div>

            </div>

            <div className="grid grid-cols-3 gap-4">

              <Input
                placeholder="Bank Name"
                value={form.bank_name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    bank_name:
                      e.target.value,
                  })
                }
              />

              <Input
                placeholder="Account Number"
                value={
                  form.bank_account_number
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    bank_account_number:
                      e.target.value,
                  })
                }
              />

              <Input
                placeholder="Account Name"
                value={
                  form.bank_account_name
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    bank_account_name:
                      e.target.value,
                  })
                }
              />

            </div>

            <div>

              <div className="mb-3 flex items-center justify-between">

                <h3 className="font-semibold">
                  PIC
                </h3>

                <Button
                  type="button"
                  onClick={addRow}
                >
                  Add PIC
                </Button>

              </div>

              <div className="space-y-3">

                {rows.map((row, index) => (
                  <div
                    key={index}
                    className="grid grid-cols-5 gap-3"
                  >
                    <Input
                      placeholder="PIC Name"
                      value={row.pic_name}
                      onChange={(e) =>
                        updateRow(
                          index,
                          "pic_name",
                          e.target.value
                        )
                      }
                    />

                    <Input
                      placeholder="Phone"
                      value={row.phone}
                      onChange={(e) =>
                        updateRow(
                          index,
                          "phone",
                          e.target.value
                        )
                      }
                    />

                    <Input
                      placeholder="Department"
                      value={row.unit}
                      onChange={(e) =>
                        updateRow(
                          index,
                          "unit",
                          e.target.value
                        )
                      }
                    />

                    <Input
                      placeholder="Items"
                      value={row.item}
                      onChange={(e) =>
                        updateRow(
                          index,
                          "item",
                          e.target.value
                        )
                      }
                    />

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        removeRow(index)
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

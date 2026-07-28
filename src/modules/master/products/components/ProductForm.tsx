import { useEffect, useState } from "react";

import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";

import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";

import {
  useItemGroups,
  useItemSubGroups,
} from "@/modules/master/item-classification/hooks/useItemClassification";

import type { Product } from "../types";

const PURCHASE_UOMS = [
  "Kg",
  "Gram",
  "Liter",
  "Ml",
  "Bottle",
  "Pcs",
  "Pack",
  "Box",
  "Can",
  "Roll",
  "Meter",
  "Set",
];

const USAGE_UOMS = [
  "Kg",
  "Gram",
  "Liter",
  "Ml",
  "Bottle",
  "Pcs",
  "Pack",
  "Box",
  "Can",
  "Roll",
  "Meter",
  "Set",
];

const DEFAULT_CONVERSION: Record<
  string,
  {
    usage: string;
    conversion: number;
  }
> = {
  Kg: {
    usage: "Gram",
    conversion: 1000,
  },

  Gram: {
    usage: "Gram",
    conversion: 1,
  },

  Liter: {
    usage: "Ml",
    conversion: 1000,
  },

  Ml: {
    usage: "Ml",
    conversion: 1,
  },

  Bottle: {
    usage: "Ml",
    conversion: 600,
  },

  Box: {
    usage: "Pcs",
    conversion: 1,
  },

  Pack: {
    usage: "Pcs",
    conversion: 1,
  },

  Pcs: {
    usage: "Pcs",
    conversion: 1,
  },

  Can: {
    usage: "Pcs",
    conversion: 1,
  },

  Roll: {
    usage: "Meter",
    conversion: 1,
  },

  Meter: {
    usage: "Meter",
    conversion: 1,
  },

  Set: {
    usage: "Set",
    conversion: 1,
  },
};

interface Props {
  open: boolean;
  product?: Product | null;
  loading?: boolean;
  onClose: () => void;
  onSubmit: (payload: any) => void;
}

export default function ProductForm({
  open,
  product,
  loading,
  onClose,
  onSubmit,
}: Props) {
  const isEdit = !!product;

  const { data: groups = [] } =
    useItemGroups();

  const [groupId, setGroupId] =
    useState<number>();

  const {
    data: subGroups = [],
  } = useItemSubGroups(groupId);

  const [form, setForm] =
    useState({
      name: "",

      group_code: "",
      group_name: "",

      subgroup_code: "",
      subgroup_name: "",

      uom: "",
      usage_uom: "",

      conversion: 1,
    });

  useEffect(() => {
    if (!open) return;

    if (!product) {
      setGroupId(undefined);

      setForm({
        name: "",

        group_code: "",
        group_name: "",

        subgroup_code: "",
        subgroup_name: "",

        uom: "",
        usage_uom: "",

        conversion: 1,
      });

      return;
    }

    const group =
      groups.find(
        (g) =>
          g.code ===
          product.group_code
      );

    setGroupId(group?.id);

    setForm({
      name: product.name,

      group_code:
        product.group_code,

      group_name:
        product.group_name,

      subgroup_code:
        product.subgroup_code,

      subgroup_name:
        product.subgroup_name,

      uom: product.uom,

      usage_uom:
        product.usage_uom,

      conversion: Number(
        product.conversion
      ),
    });
  }, [
    open,
    product,
    groups,
  ]);

  function save() {
    onSubmit({
      ...form,
      conversion: Number(
        form.conversion
      ),
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) {
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit
              ? "Edit Product"
              : "New Product"}
          </DialogTitle>
        </DialogHeader>

        <DialogBody>
          <div className="grid grid-cols-2 gap-4">

            <div className="col-span-2">
              <label className="mb-1 block text-sm font-medium">
                Product Name
              </label>

              <Input
                value={form.name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    name:
                      e.target.value,
                  })
                }
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Group
              </label>

              <select
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={groupId ?? ""}
                onChange={(e) => {
                  const id =
                    Number(
                      e.target.value
                    );

                  setGroupId(id);

                  const group =
                    groups.find(
                      (g) =>
                        g.id === id
                    );

                  setForm({
                    ...form,

                    group_code:
                      group?.code ??
                      "",

                    group_name:
                      group?.name ??
                      "",

                    subgroup_code:
                      "",

                    subgroup_name:
                      "",
                  });
                }}
              >
                <option value="">
                  Select Group
                </option>

                {groups.map(
                  (group) => (
                    <option
                      key={
                        group.id
                      }
                      value={
                        group.id
                      }
                    >
                      {group.code} -{" "}
                      {group.name}
                    </option>
                  )
                )}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Sub Group
              </label>

              <select
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={
                  form.subgroup_code
                }
                onChange={(e) => {
                  const sg =
                    subGroups.find(
                      (x) =>
                        x.code ===
                        e.target
                          .value
                    );

                  setForm({
                    ...form,

                    subgroup_code:
                      sg?.code ??
                      "",

                    subgroup_name:
                      sg?.name ??
                      "",
                  });
                }}
              >
                <option value="">
                  Select Sub Group
                </option>

                {subGroups.map(
                  (sg) => (
                    <option
                      key={sg.id}
                      value={
                        sg.code
                      }
                    >
                      {sg.code} -{" "}
                      {sg.name}
                    </option>
                  )
                )}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Purchase UOM
              </label>

              <select
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.uom}
                onChange={(e) => {
                  const value =
                    e.target.value;

                  const preset =
                    DEFAULT_CONVERSION[
                      value
                    ];

                  setForm({
                    ...form,

                    uom: value,

                    usage_uom:
                      preset?.usage ??
                      "",

                    conversion:
                      preset?.conversion ??
                      1,
                  });
                }}
              >
                <option value="">
                  Select Purchase UOM
                </option>

                {PURCHASE_UOMS.map(
                  (uom) => (
                    <option
                      key={uom}
                      value={uom}
                    >
                      {uom}
                    </option>
                  )
                )}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Usage UOM
              </label>

              <select
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={
                  form.usage_uom
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    usage_uom:
                      e.target.value,
                  })
                }
              >
                <option value="">
                  Select Usage UOM
                </option>

                {USAGE_UOMS.map(
                  (uom) => (
                    <option
                      key={uom}
                      value={uom}
                    >
                      {uom}
                    </option>
                  )
                )}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Conversion
              </label>

              <Input
                type="number"
                value={
                  form.conversion
                }
                onChange={(e) =>
                  setForm({
                    ...form,
                    conversion:
                      Number(
                        e.target
                          .value
                      ),
                  })
                }
              />
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
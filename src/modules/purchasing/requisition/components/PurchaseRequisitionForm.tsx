import { useEffect, useState } from "react";

import Dialog, {
  DialogContent,
} from "@/components/ui/Dialog";

import Button from "@/components/ui/Button";
import Textarea from "@/components/ui/Textarea";

import { productApi } from "@/modules/master/products/api/productApi";

import PurchaseRequisitionItems, {
  PurchaseRequisitionItemRow,
  Product,
} from "./PurchaseRequisitionItems";

interface Props {
  onClose: () => void;

  onSubmit: (
    payload: any
  ) => Promise<void>;
}

export default function PurchaseRequisitionForm({
  onClose,
  onSubmit,
}: Props) {

  const [notes, setNotes] =
    useState("");

  const [expiryDate, setExpiryDate] =
    useState("");

  const [saving, setSaving] =
    useState(false);

  const [
    loadingProducts,
    setLoadingProducts,
  ] =
    useState(true);

  const [
    products,
    setProducts,
  ] =
    useState<Product[]>([]);

  const [
    items,
    setItems,
  ] =
    useState<
      PurchaseRequisitionItemRow[]
    >([
      {
        product_id: 0,
        quantity: 1,
        estimated_price: 0,
      },
    ]);

  useEffect(() => {

    loadProducts();

  }, []);

  async function loadProducts() {

    try {

      const res =
        await productApi.list();

      const data =
        res.data;

      if (
        Array.isArray(data)
      ) {

        setProducts(data);

      } else if (
        Array.isArray(
          data.items
        )
      ) {

        setProducts(
          data.items
        );

      } else if (
        Array.isArray(
          data.data
        )
      ) {

        setProducts(
          data.data
        );

      } else {

        setProducts([]);

      }

    } catch (err) {

      console.error(err);

      setProducts([]);

    } finally {

      setLoadingProducts(
        false
      );

    }

  }

  async function handleSubmit(
    e: React.FormEvent,
  ) {

    e.preventDefault();

    const validItems =
      items.filter(
        (item) =>
          item.product_id > 0 &&
          item.quantity > 0 &&
          item.estimated_price >= 0,
      );

    if (
      validItems.length === 0
    ) {

      alert(
        "Please add valid products.",
      );

      return;

    }

    try {

      setSaving(true);

      await onSubmit({

        notes,
        expiry_date: expiryDate || null,

        items: validItems,

      });

      onClose();

    } finally {

      setSaving(false);

    }

  }

  return (

    <Dialog
      open
      onOpenChange={(
        open,
      ) => {

        if (!open) {

          onClose();

        }

      }}
    >

      <DialogContent
        className="
          max-w-6xl
          max-h-[90vh]
          overflow-hidden
          p-0
        "
      >

        <form
          onSubmit={
            handleSubmit
          }
          className="
            flex
            h-full
            flex-col
          "
        >

          <div
            className="
              shrink-0
              border-b
              border-slate-200
              px-6
              py-5
            "
          >

            <h2
              className="
                text-xl
                font-semibold
              "
            >

              Create Purchase Requisition

            </h2>

            <p
              className="
                mt-1
                text-sm
                text-slate-500
              "
            >

              Create a purchasing request before approval and purchase order creation.

            </p>

          </div>

          <div
            className="
              max-h-[70vh]
              overflow-y-auto
              space-y-6
              p-6
            "
          >

            <div>
              <label className="mb-2 block text-sm font-medium">
                Valid Until
              </label>
              <input
                type="date"
                value={expiryDate}
                min={new Date().toISOString().slice(0, 10)}
                onChange={(event) => setExpiryDate(event.target.value)}
                className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              />
            </div>

            <div>

              <label
                className="
                  mb-2
                  block
                  text-sm
                  font-medium
                "
              >

                Purpose / Notes

              </label>

              <Textarea
                rows={3}
                placeholder="Describe why this purchase is needed..."
                value={notes}
                onChange={(
                  e,
                ) =>
                  setNotes(
                    e.target.value,
                  )
                }
              />

            </div>

            <PurchaseRequisitionItems

              items={items}

              products={products}

              loadingProducts={
                loadingProducts
              }

              onChange={
                setItems
              }

            />

          </div>

          <div
            className="
              shrink-0
              flex
              justify-end
              gap-3
              border-t
              border-slate-200
              px-6
              py-4
            "
          >

            <Button
              type="button"
              variant="outline"
              onClick={
                onClose
              }
            >

              Cancel

            </Button>

            <Button
              type="submit"
              loading={
                saving
              }
            >

              Create Purchase Requisition

            </Button>

          </div>

        </form>

      </DialogContent>

    </Dialog>

  );

}
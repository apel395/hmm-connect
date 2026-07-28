import { useState } from "react";

import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";

import SupplierTable from "../components/SupplierTable";
import SupplierForm from "../components/SupplierForm";
import SupplierProductTable from "../components/SupplierProductTable";
import SupplierProductForm from "../components/SupplierProductForm";

import type { Supplier } from "../types";

import {
  useSuppliers,
  useCreateSupplier,
  useUpdateSupplier,
  useDeleteSupplier,
} from "../hooks/useSuppliers";

import {
  useSupplierProducts,
  useCreateSupplierProduct,
  useDeleteSupplierProduct,
} from "../hooks/useSupplierProducts";

export default function SupplierPage() {
  const {
    data = [],
    isLoading,
  } = useSuppliers();

  const createMutation =
    useCreateSupplier();

  const updateMutation =
    useUpdateSupplier();

  const deleteMutation =
    useDeleteSupplier();

  const createSupplierProduct =
    useCreateSupplierProduct();

  const deleteSupplierProduct =
    useDeleteSupplierProduct();

  const [open, setOpen] =
    useState(false);

  const [
    productOpen,
    setProductOpen,
  ] = useState(false);

  const [selected, setSelected] =
    useState<Supplier | null>(null);

  const {
    data: supplierProducts = [],
  } = useSupplierProducts(
    selected?.id
  );

  function createSupplier() {
    setSelected(null);
    setOpen(true);
  }

  function editSupplier(
    supplier: Supplier
  ) {
    setSelected(supplier);
    setOpen(true);
  }

  function manageProducts(
    supplier: Supplier
  ) {
    setSelected(supplier);
  }

  async function submit(
    payload: any
  ) {
    try {
      if (selected) {
        await updateMutation.mutateAsync({
          id: selected.id,
          payload,
        });
      } else {
        await createMutation.mutateAsync(
          payload
        );
      }

      setOpen(false);
      setSelected(null);
    } catch (err) {
      console.error(err);
    }
  }

  async function remove(
    supplier: Supplier
  ) {
    if (
      !window.confirm(
        `Delete supplier "${supplier.name}"?`
      )
    ) {
      return;
    }

    try {
      await deleteMutation.mutateAsync(
        supplier.id
      );

      if (
        selected?.id === supplier.id
      ) {
        setSelected(null);
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function addProduct(
    payload: any
  ) {
    if (!selected) return;

    try {
      await createSupplierProduct.mutateAsync(
        {
          supplierId:
            selected.id,
          payload,
        }
      );

      setProductOpen(false);
    } catch (err) {
      console.error(err);
    }
  }

  async function removeProduct(
    row: any
  ) {
    if (!selected) return;

    if (
      !window.confirm(
        `Remove "${row.product_name}"?`
      )
    ) {
      return;
    }

    try {
      await deleteSupplierProduct.mutateAsync(
        {
          supplierId:
            selected.id,
          id: row.id,
        }
      );
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <>
      <div className="space-y-6">

        <PageHeader
          title="Suppliers"
          description="Supplier Master"
          action={
            <Button
              onClick={
                createSupplier
              }
            >
              New Supplier
            </Button>
          }
        />

        <Card>
          {isLoading ? (
            <Loading />
          ) : (
            <SupplierTable
              rows={data}
              onEdit={
                editSupplier
              }
              onDelete={
                remove
              }
              onProducts={
                manageProducts
              }
            />
          )}
        </Card>

        {selected && (
          <Card>

            <div className="mb-5 flex items-center justify-between">

              <div>

                <h2 className="text-lg font-semibold">
                  Supplier Products
                </h2>

                <p className="text-sm text-slate-500">
                  {selected.code}
                  {" - "}
                  {selected.name}
                </p>

              </div>

              <Button
                onClick={() =>
                  setProductOpen(
                    true
                  )
                }
              >
                Add Product
              </Button>

            </div>

            <SupplierProductTable
              rows={
                supplierProducts
              }
              onDelete={
                removeProduct
              }
            />

          </Card>
        )}

      </div>

      <SupplierForm
        open={open}
        supplier={selected}
        loading={
          createMutation.isPending ||
          updateMutation.isPending
        }
        onClose={() => {
          setOpen(false);
          setSelected(null);
        }}
        onSubmit={submit}
      />

      <SupplierProductForm
        open={productOpen}
        loading={
          createSupplierProduct.isPending
        }
        onClose={() =>
          setProductOpen(false)
        }
        onSubmit={addProduct}
      />
    </>
  );
}
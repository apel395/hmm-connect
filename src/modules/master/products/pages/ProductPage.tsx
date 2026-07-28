import { useState } from "react";

import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import ConfirmDialog from "@/components/common/ConfirmDialog";

import ProductTable from "../components/ProductTable";
import ProductForm from "../components/ProductForm";

import type { Product } from "../types";

import {
  useProducts,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
} from "../hooks/useProducts";

export default function ProductPage() {
  const {
    data = [],
    isLoading,
  } = useProducts();

  const createMutation =
    useCreateProduct();

  const updateMutation =
    useUpdateProduct();

  const deleteMutation =
    useDeleteProduct();

  const [formOpen, setFormOpen] =
    useState(false);

  const [selected, setSelected] =
    useState<Product | null>(null);

  const [deleteOpen, setDeleteOpen] =
    useState(false);

  function handleCreate() {
    setSelected(null);
    setFormOpen(true);
  }

  function handleEdit(
    product: Product
  ) {
    setSelected(product);
    setFormOpen(true);
  }

  function handleDelete(
    product: Product
  ) {
    setSelected(product);
    setDeleteOpen(true);
  }

  async function handleSubmit(
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

      setFormOpen(false);
      setSelected(null);
    } catch (err) {
      console.error(err);
    }
  }

  async function confirmDelete() {
    if (!selected) return;

    try {
      await deleteMutation.mutateAsync(
        selected.id
      );

      setDeleteOpen(false);
      setSelected(null);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <>
      <div className="space-y-6">

        <PageHeader
          title="Products"
          description="Product Master"
          actions={
            <Button
              onClick={
                handleCreate
              }
            >
              New Product
            </Button>
          }
        />

        <Card>
          {isLoading ? (
            <Loading />
          ) : (
            <ProductTable
              rows={data}
              onEdit={
                handleEdit
              }
              onDelete={
                handleDelete
              }
            />
          )}
        </Card>
      </div>

      <ProductForm
        open={formOpen}
        product={selected}
        loading={
          createMutation.isPending ||
          updateMutation.isPending
        }
        onClose={() => {
          setFormOpen(false);
          setSelected(null);
        }}
        onSubmit={handleSubmit}
      />

      {/* <ConfirmDialog
        open={deleteOpen}
        title="Delete Product"
        confirmText="Delete"
        loading={
          deleteMutation.isPending
        }
        onCancel={() => {
          setDeleteOpen(false);
          setSelected(null);
        }}
        onConfirm={confirmDelete}
      /> */}
    </>
  );
}
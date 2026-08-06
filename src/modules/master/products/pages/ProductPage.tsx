import { useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import ProductTable from "../components/ProductTable";
import ProductForm from "../components/ProductForm";
import type { Product } from "../types";
import { useProducts, useCreateProduct, useUpdateProduct, useDeleteProduct } from "../hooks/useProducts";

export default function ProductPage() {
  const { data = [], isLoading } = useProducts();
  const createMutation = useCreateProduct();
  const updateMutation = useUpdateProduct();
  const deleteMutation = useDeleteProduct();
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<Product | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const handleCreate = () => { setSelected(null); setFormOpen(true); };
  const handleEdit = (product:Product) => { setSelected(product); setFormOpen(true); };
  const handleDelete = (product:Product) => { setSelected(product); setDeleteOpen(true); };
  const handleSubmit = async (payload:any) => {
    if (selected) await updateMutation.mutateAsync({id:selected.id, payload});
    else await createMutation.mutateAsync(payload);
    setFormOpen(false); setSelected(null);
  };
  const confirmDelete = async () => {
    if (!selected) return;
    await deleteMutation.mutateAsync(selected.id);
    setDeleteOpen(false); setSelected(null);
  };

  return <>
    <div className="space-y-6">
      <PageHeader title="Products" description="Product Master" actions={<Button onClick={handleCreate}>New Product</Button>}/>
      <Card>{isLoading ? <Loading/> : <ProductTable rows={data} onEdit={handleEdit} onDelete={handleDelete}/>}</Card>
    </div>
    <ProductForm open={formOpen} product={selected} products={data} loading={createMutation.isPending || updateMutation.isPending} onClose={() => {setFormOpen(false);setSelected(null);}} onSubmit={handleSubmit}/>
    <ConfirmDialog open={deleteOpen} title="Delete Product" message={`Delete ${selected?.name ?? "this product"}?`} confirmText="Delete" loading={deleteMutation.isPending} onClose={() => {setDeleteOpen(false);setSelected(null);}} onConfirm={confirmDelete}/>
  </>;
}

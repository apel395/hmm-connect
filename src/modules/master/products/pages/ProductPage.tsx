import { useEffect, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import ProductTable from "../components/ProductTable";
import ProductForm from "../components/ProductForm";
import type { Product } from "../types";
import { useProducts, useCreateProduct, useUpdateProduct } from "../hooks/useProducts";

const PAGE_SIZE = 25;

export default function ProductPage() {
  const { data = [], isLoading } = useProducts();
  const createMutation = useCreateProduct();
  const updateMutation = useUpdateProduct();
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<Product | null>(null);
  const [page, setPage] = useState(1);
  const pages = Math.max(Math.ceil(data.length / PAGE_SIZE), 1);
  const pageRows = data.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    if (page > pages) setPage(pages);
  }, [page, pages]);

  const handleCreate = () => { setSelected(null); setFormOpen(true); };
  const handleEdit = (product:Product) => { setSelected(product); setFormOpen(true); };
  const handleSubmit = async (payload:any) => {
    if (selected) await updateMutation.mutateAsync({id:selected.id, payload});
    else await createMutation.mutateAsync(payload);
    setFormOpen(false); setSelected(null);
  };

  return <>
    <div className="space-y-6">
      <PageHeader title="Products" description="Product Master" actions={<Button onClick={handleCreate}>New Product</Button>}/>
      <Card>
        {isLoading ? <Loading/> : <>
          <ProductTable rows={pageRows} onEdit={handleEdit}/>
          <Pagination page={page} pages={pages} total={data.length} pageSize={PAGE_SIZE} noun="products" onChange={setPage}/>
        </>}
      </Card>
    </div>
    <ProductForm open={formOpen} product={selected} products={data} loading={createMutation.isPending || updateMutation.isPending} onClose={() => {setFormOpen(false);setSelected(null);}} onSubmit={handleSubmit}/>
  </>;
}

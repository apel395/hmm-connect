import { useEffect, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import SearchBox from "@/components/datatable/SearchBox";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import ProductTable from "../components/ProductTable";
import ProductForm from "../components/ProductForm";
import type { Product } from "../types";
import { useProducts, useCreateProduct, useUpdateProduct } from "../hooks/useProducts";

const PAGE_SIZE = 25;

export default function ProductPage() {
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<Product | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const query = useProducts({ page, page_size: PAGE_SIZE, search: search || undefined });
  const createMutation = useCreateProduct();
  const updateMutation = useUpdateProduct();
  const data = query.data ?? {};
  const rows: Product[] = data.items ?? [];
  const pages = Math.max(data.total_pages ?? 0, 1);
  const total = data.total_items ?? 0;

  useEffect(() => {
    setPage(1);
  }, [search]);

  useEffect(() => {
    if (page > pages) setPage(pages);
  }, [page, pages]);

  const handleCreate = () => { setSelected(null); setFormOpen(true); };
  const handleEdit = (product: Product) => { setSelected(product); setFormOpen(true); };
  const handleSubmit = async (payload: any) => {
    if (selected) await updateMutation.mutateAsync({ id: selected.id, payload });
    else await createMutation.mutateAsync(payload);
    setFormOpen(false);
    setSelected(null);
  };

  return <>
    <div className="space-y-6">
      <PageHeader title="Products" description="Product Master" actions={<Button onClick={handleCreate}>New Product</Button>}/>
      <Card>
        <div className="mb-4 max-w-md">
          <SearchBox value={search} onChange={setSearch} placeholder="Search item code or name..." />
        </div>
        {query.isLoading ? <Loading/> : <>
          <ProductTable rows={rows} onEdit={handleEdit}/>
          <Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="products" onChange={setPage}/>
        </>}
      </Card>
    </div>
    <ProductForm open={formOpen} product={selected} products={rows} loading={createMutation.isPending || updateMutation.isPending} onClose={() => { setFormOpen(false); setSelected(null); }} onSubmit={handleSubmit}/>
  </>;
}

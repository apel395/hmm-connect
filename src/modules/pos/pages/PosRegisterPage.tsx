import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Minus, Plus, Receipt, ShoppingCart, Trash2 } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import SearchableSelect from "@/components/form/SearchableSelect";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";
import { posApi, type PosItemIn, type PosPaymentMethod, type PosTransactionType } from "../api";
import { warehouseApi } from "@/modules/master/warehouses/api/warehouseApi";

const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

interface CartLine { product_id: number; product_code: string; product_name: string; group_name: string; uom: string; quantity: number; unit_price: number; service_charge_rate: number; tax_rate: number; is_taxable: boolean; stock: number; }

export default function PosRegisterPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const canSell = canAccess(user, POS_ROLES, "pos.sell");
  const [transactionType, setTransactionType] = useState<PosTransactionType>("POS");
  const [warehouseId, setWarehouseId] = useState<number | undefined>();
  const [tableNumber, setTableNumber] = useState("");
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [discount, setDiscount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PosPaymentMethod>("CASH");
  const [amountReceived, setAmountReceived] = useState("");
  const [error, setError] = useState("");
  const [queueNumber, setQueueNumber] = useState("");
  const [lastNumber, setLastNumber] = useState("");

  const warehousesQuery = useQuery({ queryKey: ["pos-warehouses"], queryFn: async () => (await warehouseApi.list()).data });
  const warehouses: any[] = useMemo(() => warehousesQuery.data ?? [], [warehousesQuery.data]);
  const warehouseOptions = warehouses.map((w) => ({ id: w.id, code: w.code, name: w.name }));
  useEffect(() => { if (!warehouseId && warehouses.length) setWarehouseId(warehouses[0].id); }, [warehouses, warehouseId]);

  const productsQuery = useQuery({
    queryKey: ["pos-products", warehouseId, search],
    queryFn: async () => (await posApi.products({ warehouse_id: warehouseId, search: search.trim() || undefined, page: 1, page_size: 200 })).data,
    enabled: Boolean(warehouseId),
  });
  const products: any[] = useMemo(() => productsQuery.data?.items ?? [], [productsQuery.data?.items]);
  const groups = useMemo(() => Array.from(new Set(products.map((p) => p.group_name).filter(Boolean))) as string[], [products]);
  const visibleProducts = groupFilter ? products.filter((p) => p.group_name === groupFilter) : products;
  const subtotal = cart.reduce((sum, line) => sum + line.quantity * line.unit_price, 0);
  const tax = cart.reduce((sum, line) => sum + (line.is_taxable && line.tax_rate > 0 ? line.quantity * line.unit_price * line.tax_rate / 100 : 0), 0);
  const discountValue = Math.min(Number(discount) || 0, subtotal);
  const serviceCharge=cart.reduce((sum,line)=>sum+Math.round(line.quantity*line.unit_price*line.service_charge_rate)/100,0);
  const total = subtotal - discountValue + tax + serviceCharge;
  const change = paymentMethod === "CASH" ? Math.max((Number(amountReceived) || 0) - total, 0) : 0;
  const inCart = (id: number) => cart.find((line) => line.product_id === id);

  const addToCart = (product: any) => {
    setError("");
    const existing = inCart(product.product_id);
    if (existing) {
      if (existing.quantity >= Number(product.quantity ?? 0)) return;
      setCart((rows) => rows.map((line) => line.product_id === product.product_id ? { ...line, quantity: line.quantity + 1 } : line));
      return;
    }
    setCart((rows) => [...rows, { product_id: product.product_id, product_code: product.product_code, product_name: product.product_name, group_name: product.group_name, uom: product.uom, quantity: 1, unit_price: Number(product.selling_price ?? 0), service_charge_rate:Number(product.service_charge_rate??0), tax_rate: Number(product.tax_rate ?? 0), is_taxable: Boolean(product.is_taxable), stock: Number(product.quantity ?? 0) }]);
  };
  const changeQty = (id: number, delta: number) => setCart((rows) => rows.map((line) => line.product_id === id ? { ...line, quantity: Math.max(0, Math.min(line.stock, line.quantity + delta)) } : line).filter((line) => line.quantity > 0));
  const clear = () => { setCart([]); setDiscount(""); setAmountReceived(""); setQueueNumber(""); setLastNumber(""); };

  const createAndPost = useMutation({
    mutationFn: async () => {
      const created = (await posApi.create({ warehouse_id: warehouseId!, transaction_type: transactionType, items: cart.map((line): PosItemIn => ({ product_id: line.product_id, quantity: line.quantity })) })).data;
      const metadata = await posApi.metadata(created.id, { transaction_type: transactionType, table_number: transactionType === "POS" ? tableNumber.trim() : null, queue_number: created.transaction_number });
      const posted = (await posApi.post(created.id, { payment_method: paymentMethod, payment_received: paymentMethod === "CASH" ? Number(amountReceived) : total, discount_amount: discountValue > 0 ? discountValue : null })).data;
      return { created, metadata: metadata.data, posted };
    },
    onSuccess: ({ created, metadata }) => { setQueueNumber(metadata.queue_number || created.transaction_number); setLastNumber(created.transaction_number); setCart([]); setDiscount(""); setAmountReceived(""); void queryClient.invalidateQueries({ queryKey: ["pos-products"] }); },
    onError: (e: any) => setError(e?.response?.data?.detail || e?.message || "Transaction failed"),
  });

  const saveDraft = useMutation({
    mutationFn: async () => {
      const created = (await posApi.create({ warehouse_id: warehouseId!, transaction_type: transactionType, items: cart.map((line): PosItemIn => ({ product_id: line.product_id, quantity: line.quantity })) })).data;
      return posApi.metadata(created.id, { transaction_type: transactionType, table_number: transactionType === "POS" ? tableNumber.trim() : null, queue_number: created.transaction_number });
    },
    onSuccess: () => navigate("/pos/sales"),
    onError: (e: any) => setError(e?.response?.data?.detail || e?.message || "Could not save draft"),
  });

  const checkout = () => {
    setError("");
    if (!canSell) return setError("You do not have permission to sell.");
    if (!warehouseId) return setError("Select a warehouse.");
    if (transactionType === "POS" && !tableNumber.trim()) return setError("Select or enter a table number.");
    if (!cart.length) return setError("Add at least one menu item.");
    if (paymentMethod === "CASH" && Number(amountReceived) < total) return setError("Cash received must cover the total.");
    createAndPost.mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Point of Sales" description="POS uses table service and queue numbers. Direct Invoice skips the table and creates an invoice immediately." />
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setTransactionType("POS")} className={`rounded-lg px-4 py-2 text-sm font-semibold ${transactionType === "POS" ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600"}`}>POS · Meja</button>
          <button type="button" onClick={() => setTransactionType("INVOICE")} className={`rounded-lg px-4 py-2 text-sm font-semibold ${transactionType === "INVOICE" ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600"}`}>Invoice · Langsung</button>
          <div className="ml-auto text-xs text-slate-500">{transactionType === "POS" ? "Pilih meja → pilih menu → ambil nomor → bayar" : "Pilih menu → bayar → invoice langsung"}</div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <SearchableSelect label="Warehouse" required value={warehouseId} options={warehouseOptions} placeholder="Select warehouse" onChange={(value) => setWarehouseId(value)} />
          {transactionType === "POS" ? <div><label className="mb-1 block text-xs font-medium text-slate-500">Meja <span className="text-red-500">*</span></label><input className={input} value={tableNumber} onChange={(e) => setTableNumber(e.target.value)} placeholder="Contoh: M-01 / 12" /></div> : <div className="rounded-md border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">Invoice langsung tidak memerlukan meja.</div>}
        </div>
      </Card>
      {queueNumber && <Card className="flex items-center justify-between border-emerald-200 bg-emerald-50 p-4"><div><div className="text-xs uppercase tracking-wide text-emerald-700">{transactionType === "POS" ? "Nomor Antrian" : "Nomor Invoice"}</div><div className="mt-1 text-2xl font-bold text-emerald-800">{queueNumber}</div></div>{transactionType === "POS" && <Badge variant="success">Meja {tableNumber}</Badge>}</Card>}

      <div className="grid gap-4 lg:grid-cols-[1fr_390px]">
        <Card className="p-4">
          <input className={`${input} mb-3`} placeholder="Cari menu, kode atau kategori" value={search} onChange={(e) => setSearch(e.target.value)} />
          {groups.length > 0 && <div className="mb-3 flex flex-wrap gap-1.5"><button type="button" onClick={() => setGroupFilter("")} className={`rounded-full px-3 py-1 text-xs font-medium ${!groupFilter ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600"}`}>All</button>{groups.map((g) => <button key={g} type="button" onClick={() => setGroupFilter(g)} className={`rounded-full px-3 py-1 text-xs font-medium ${groupFilter === g ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600"}`}>{g}</button>)}</div>}
          {productsQuery.isLoading ? <Loading /> : <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">{visibleProducts.map((product) => <button key={product.product_id} type="button" disabled={Number(product.quantity) <= 0} onClick={() => addToCart(product)} className="flex h-24 flex-col justify-between rounded-lg border border-slate-200 p-2.5 text-left hover:border-[#0F6758] disabled:opacity-40"><div><div className="line-clamp-2 text-xs font-semibold">{product.product_name}</div><div className="text-[10px] text-slate-400">{product.group_name || product.product_code}</div></div><div className="flex items-center justify-between"><span className="text-sm font-bold text-[#0F6758]">{money(product.selling_price)}</span><span className="text-[10px] text-slate-500">{num(product.quantity)} {product.uom}</span></div></button>)}</div>}
        </Card>
        <Card className="h-fit p-4">
          <div className="mb-3 flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-semibold"><ShoppingCart className="h-4 w-4 text-[#0F6758]" />Order</div>{cart.length > 0 && <button type="button" onClick={clear} className="text-xs text-slate-500">Clear</button>}</div>
          <div className="space-y-2">{cart.length === 0 && <div className="rounded-md border border-dashed p-6 text-center text-xs text-slate-500">Pilih menu untuk memulai.</div>}{cart.map((line) => <div key={line.product_id} className="rounded-md border p-2"><div className="flex justify-between gap-2"><div className="min-w-0"><div className="truncate text-xs font-semibold">{line.product_name}</div><div className="text-[10px] text-slate-400">{money(line.unit_price)} / {line.uom}</div></div><button type="button" onClick={() => changeQty(line.product_id, -line.quantity)} className="text-slate-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></button></div><div className="mt-2 flex items-center justify-between"><div className="flex items-center gap-1"><button type="button" onClick={() => changeQty(line.product_id, -1)} className="grid h-7 w-7 place-items-center rounded border"><Minus className="h-3.5 w-3.5" /></button><span className="w-8 text-center text-sm">{line.quantity}</span><button type="button" onClick={() => changeQty(line.product_id, 1)} className="grid h-7 w-7 place-items-center rounded border"><Plus className="h-3.5 w-3.5" /></button></div><span className="text-sm font-semibold">{money(line.quantity * line.unit_price)}</span></div></div>)}</div>
          <div className="mt-4 space-y-2 border-t pt-3 text-sm"><div className="flex justify-between"><span>Subtotal</span><span>{money(subtotal)}</span></div><div className="flex items-center justify-between"><span>Discount</span><input className="h-9 w-32 rounded border px-2 text-right" type="number" min={0} value={discount} onChange={(e) => setDiscount(e.target.value)} /></div><div className="flex justify-between"><span>Service charge</span><span>{money(serviceCharge)}</span></div><div className="flex justify-between"><span>PPN</span><span>{money(tax)}</span></div><div className="flex justify-between border-t pt-2 text-base font-bold"><span>Total</span><span>{money(total)}</span></div></div>
          <div className="mt-4 space-y-2"><select className={input} value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PosPaymentMethod)}><option value="CASH">Cash</option><option value="CARD">Card</option><option value="BANK_TRANSFER">Bank Transfer</option></select>{paymentMethod === "CASH" && <><input className={input} type="number" min={0} placeholder="Cash received" value={amountReceived} onChange={(e) => setAmountReceived(e.target.value)} /><div className="flex justify-between text-xs text-slate-500"><span>Change</span><span>{money(change)}</span></div></>}</div>
          {error && <div className="mt-3 rounded-md bg-red-50 p-2 text-xs text-red-700">{error}</div>}
          {lastNumber && <div className="mt-3 rounded-md bg-emerald-50 p-2 text-xs text-emerald-700">Saved: <strong>{lastNumber}</strong></div>}
          <div className="mt-4 grid grid-cols-2 gap-2"><Button variant="outline" disabled={!cart.length || saveDraft.isPending} onClick={() => saveDraft.mutate()}>Save Draft</Button><Button variant="primary" disabled={!cart.length || createAndPost.isPending} onClick={checkout}><Receipt className="h-4 w-4" /> {transactionType === "POS" ? "Ambil Nomor & Bayar" : "Create Invoice"}</Button></div>
        </Card>
      </div>
    </div>
  );
}

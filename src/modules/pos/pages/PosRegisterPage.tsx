import { useMemo, useState } from "react";
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
import useFormRecovery from "@/hooks/useFormRecovery";
import { browserDraftStorage, draftKey, readDraft } from "@/utils/formDraftStorage";
import { canAccess } from "@/lib/access";
import { posApi, type PosItemIn, type PosPaymentMethod, type PosTransactionType } from "../api";

const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

interface CartLine { sales_location_id?: number; sales_business_unit_id?: number; department_id?: number; catalog_type?: string; product_id: number; product_code: string; product_name: string; group_name: string; uom: string; quantity: number; unit_price: number; service_charge_rate: number; tax_rate: number; tax_type?: string; is_taxable: boolean; sale_available: boolean; }

type PosDraft = { orderLocationId?: number; orderDepartmentId?: number; revenueAccountId?: number; pendingDraftId?: number; transactionType: PosTransactionType; locationId?: number; departmentId?: number; tableNumber: string; search: string; groupFilter: string; cart: CartLine[]; discount: string; paymentMethod: PosPaymentMethod; amountReceived: string };
const validDraft = (value: unknown): value is PosDraft => {
  if (!value || typeof value !== "object") return false;
  const d = value as PosDraft;
  return ["POS", "INVOICE"].includes(d.transactionType) && ["CASH", "CARD", "BANK_TRANSFER"].includes(d.paymentMethod)
    && [d.tableNumber, d.search, d.groupFilter, d.discount, d.amountReceived].every(v => typeof v === "string")
    && [d.locationId, d.departmentId, d.orderLocationId, d.orderDepartmentId, d.revenueAccountId, d.pendingDraftId].every(v => v === undefined || (Number.isInteger(v) && v > 0))
    && Array.isArray(d.cart) && d.cart.every(l => l && Number.isInteger(l.product_id) && l.product_id > 0
      && [l.quantity, l.unit_price, l.service_charge_rate, l.tax_rate].every(v => Number.isFinite(v) && v >= 0)
      && l.quantity > 0 && [l.product_code, l.product_name, l.group_name, l.uom].every(v => typeof v === "string")
      && typeof l.is_taxable === "boolean" && typeof l.sale_available === "boolean");
};
export default function PosRegisterPage() {
  const owner = useAuthStore(state => state.user?.id ?? state.user?.username);
  return <PosRegister key={owner ?? "anonymous"} />;
}
function PosRegister() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [initial] = useState(() => {
    const owner = user?.id ?? user?.username, storage = browserDraftStorage();
    return owner != null && storage ? readDraft(storage, draftKey(String(owner), "pos:register"), validDraft) : null;
  });
  const canSell = canAccess(user, POS_ROLES, "pos.sell");
  const [transactionType, setTransactionType] = useState<PosTransactionType>(initial?.transactionType ?? "POS");
  const [locationId, setLocationId] = useState<number | undefined>(initial?.locationId);
  const [tableNumber, setTableNumber] = useState(initial?.tableNumber ?? "");
  const [search, setSearch] = useState(initial?.search ?? "");
  const [groupFilter, setGroupFilter] = useState(initial?.groupFilter ?? "");
  const [cart, setCart] = useState<CartLine[]>(initial?.cart ?? []);
  const [discount, setDiscount] = useState(initial?.discount ?? "");
  const [paymentMethod, setPaymentMethod] = useState<PosPaymentMethod>(initial?.paymentMethod ?? "CASH");
  const [amountReceived, setAmountReceived] = useState(initial?.amountReceived ?? "");
  const [error, setError] = useState("");
  const [queueNumber, setQueueNumber] = useState("");
  const [lastNumber, setLastNumber] = useState("");

  const [departmentId, setDepartmentId] = useState<number | undefined>(initial?.departmentId);
  const [orderLocationId, setOrderLocationId] = useState<number | undefined>(initial?.orderLocationId ?? (initial?.cart.length ? initial.locationId : undefined));
  const [orderDepartmentId, setOrderDepartmentId] = useState<number | undefined>(initial?.orderDepartmentId ?? (initial?.cart.length ? initial.departmentId : undefined));
  const [revenueAccountId, setRevenueAccountId] = useState<number | undefined>(initial?.revenueAccountId);
  const [pendingDraftId, setPendingDraftId] = useState<number | undefined>(initial?.pendingDraftId);
  const saleLocationId = cart.find(line => line.sales_location_id)?.sales_location_id ?? orderLocationId;
  const saleDepartmentId = cart.find(line => line.department_id)?.department_id ?? orderDepartmentId;
  const recovery = useFormRecovery("pos:register", { transactionType, locationId, departmentId, orderLocationId, orderDepartmentId, revenueAccountId, pendingDraftId, tableNumber, search, groupFilter, cart, discount, paymentMethod, amountReceived }, true, validDraft);
  const optionsQuery = useQuery({ queryKey: ["pos-options", user?.id], queryFn: async () => (await posApi.options()).data });
  const locations = useMemo(() => optionsQuery.data?.locations ?? [], [optionsQuery.data]);
  const departments = useMemo(() => (optionsQuery.data?.departments ?? []).filter((d: any) => !locationId || d.location_id === locationId).filter((d: any, i: number, all: any[]) => all.findIndex(x => x.id === d.id) === i), [optionsQuery.data, locationId]);
  const orderDepartments = useMemo(() => (optionsQuery.data?.departments ?? []).filter((d: any) => d.location_id === saleLocationId), [optionsQuery.data, saleLocationId]);
  const revenueQuery = useQuery({ queryKey: ["pos-revenue-accounts", user?.id, saleLocationId], queryFn: async () => (await posApi.revenueAccounts(saleLocationId)).data });
  const revenueAccounts = useMemo(() => revenueQuery.data ?? [], [revenueQuery.data]);

  const productsQuery = useQuery({
    queryKey: ["pos-products", user?.id, locationId, departmentId, search],
    queryFn: async () => {
      const items = [];
      let page = 1, hasNext = true;
      while (hasNext) {
        const { data } = await posApi.products({ location_id: locationId, department_id: departmentId, search: search.trim() || undefined, page, page_size: 200 });
        items.push(...data.items);
        hasNext = data.has_next;
        page += 1;
      }
      return { items };
    },
  });
  const products: any[] = useMemo(() => productsQuery.data?.items ?? [], [productsQuery.data?.items]);
  const groups = useMemo(() => Array.from(new Set(products.map((p) => p.group_name).filter(Boolean))) as string[], [products]);
  const visibleProducts = groupFilter ? products.filter((p) => p.group_name === groupFilter) : products;
  const subtotal = cart.reduce((sum, line) => sum + line.quantity * line.unit_price, 0);
  const discountValue = Math.max(0, Math.min(Number(discount) || 0, subtotal));
  let allocatedDiscount = 0;
  const tax = cart.reduce((sum, line, index) => {
    const gross = Math.round(line.quantity * line.unit_price * 100) / 100;
    const share = index === cart.length - 1 ? discountValue - allocatedDiscount : Math.min(discountValue - allocatedDiscount, Math.round(discountValue * gross / (subtotal || 1) * 100) / 100);
    allocatedDiscount += share;
    const base = line.tax_type === "PBJT" ? Math.max(0, gross - share + Math.round(gross * line.service_charge_rate) / 100) : gross;
    return sum + (line.is_taxable ? Math.round(base * line.tax_rate) / 100 : 0);
  }, 0);
  const taxLabel = cart.some(line => line.tax_type === "PBJT") ? (cart.some(line => line.is_taxable && line.tax_type !== "PBJT") ? "PBJT / PPN" : "PBJT") : "Tax";
  const serviceCharge=cart.reduce((sum,line)=>sum+Math.round(line.quantity*line.unit_price*line.service_charge_rate)/100,0);
  const total = subtotal - discountValue + tax + serviceCharge;
  const change = paymentMethod === "CASH" ? Math.max((Number(amountReceived) || 0) - total, 0) : 0;
  const inCart = (id: number) => cart.find((line) => line.product_id === id);

  const addToCart = (product: any) => {
    setError("");
    if (!product.sale_available) return;
    const conflict = cart.length > 0 && (
      (product.sales_location_id && saleLocationId && product.sales_location_id !== saleLocationId)
      || (product.department_id && saleDepartmentId && product.department_id !== saleDepartmentId)
      || cart.some(line => (line.catalog_type && product.catalog_type && line.catalog_type !== product.catalog_type)
        || (line.sales_business_unit_id && product.sales_business_unit_id && line.sales_business_unit_id !== product.sales_business_unit_id)));
    if (conflict) return setError("This menu belongs to another location, business unit or department. Use a separate order.");
    if (!cart.length) { setOrderLocationId(product.sales_location_id); setOrderDepartmentId(product.department_id); setRevenueAccountId(undefined); }
    const existing = inCart(product.product_id);
    if (existing) {
      setCart((rows) => rows.map((line) => line.product_id === product.product_id ? { ...line, quantity: line.quantity + 1 } : line));
      return;
    }
    setCart((rows) => [...rows, { sales_location_id: product.sales_location_id ?? undefined, sales_business_unit_id: product.sales_business_unit_id ?? undefined, department_id: product.department_id ?? undefined, catalog_type: product.catalog_type, product_id: product.product_id, product_code: product.product_code, product_name: product.product_name, group_name: product.group_name, uom: product.uom, quantity: 1, unit_price: Number(product.selling_price ?? 0), service_charge_rate:Number(product.service_charge_rate??0), tax_rate: Number(product.tax_rate ?? 0), tax_type: product.tax_type, is_taxable: Boolean(product.is_taxable), sale_available: Boolean(product.sale_available) }]);
  };
  const changeQty = (id: number, delta: number) => {
    const next = cart.map(line => line.product_id === id ? { ...line, quantity: Math.max(0, line.quantity + delta) } : line).filter(line => line.quantity > 0);
    if (!next.length) { clear(); return; }
    setCart(next);
  };
  const clear = () => { recovery.clear(); setCart([]); setPendingDraftId(undefined); setOrderLocationId(undefined); setOrderDepartmentId(undefined); setRevenueAccountId(undefined); setDiscount(""); setAmountReceived(""); setQueueNumber(""); setLastNumber(""); };

  const persistOrder = async () => {
    if (!saleLocationId) throw new Error("Choose the order location for menus shared across locations.");
    if (!revenueAccountId) throw new Error("Choose a revenue account.");
    const items = cart.map((line): PosItemIn => ({ product_id: line.product_id, quantity: line.quantity }));
    let created;
    if (pendingDraftId) {
      created = (await posApi.update(pendingDraftId, { revenue_account_id: revenueAccountId, items })).data;
    } else {
      created = (await posApi.create({ location_id: saleLocationId, department_id: saleDepartmentId, revenue_account_id: revenueAccountId, transaction_type: transactionType, items })).data;
      setPendingDraftId(created.id);
    }
    const metadata = (await posApi.metadata(created.id, { transaction_type: transactionType, table_number: transactionType === "POS" ? tableNumber.trim() : null, queue_number: created.transaction_number })).data;
    return { created, metadata };
  };
  const createAndPost = useMutation({
    mutationFn: async () => {
      const { created, metadata } = await persistOrder();
      const posted = (await posApi.post(created.id, { revenue_account_id: revenueAccountId, payment_method: paymentMethod, payment_received: paymentMethod === "CASH" ? Number(amountReceived) : total, discount_amount: discountValue > 0 ? discountValue : null })).data;
      return { created, metadata, posted };
    },
    onSuccess: ({ created, metadata }) => { clear(); setQueueNumber(metadata.queue_number || created.transaction_number); setLastNumber(metadata.transaction_number || created.transaction_number); void queryClient.invalidateQueries({ queryKey: ["pos-products"] }); },
    onError: (e: any) => setError(e?.response?.data?.detail || e?.message || "Transaction failed"),
  });
  const saveDraft = useMutation({
    mutationFn: persistOrder,
    onSuccess: () => { clear(); navigate("/pos/sales"); },
    onError: (e: any) => setError(e?.response?.data?.detail || e?.message || "Could not save draft"),
  });

  const checkout = () => {
    setError("");
    if (!canSell) return setError("You do not have permission to sell.");
    if (!saleLocationId) return setError("Choose the order sales location.");
    if (!revenueAccountId) return setError("Choose a revenue account.");
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
          <SearchableSelect label="Filter location" value={locationId} options={locations} placeholder="All accessible locations" onChange={(value) => { setLocationId(value); setDepartmentId(undefined); setGroupFilter(""); }} />
          <SearchableSelect label="Filter department / outlet" value={departmentId} options={departments} placeholder="All departments / outlets" onChange={(value) => { setDepartmentId(value); setGroupFilter(""); }} />
          {transactionType === "POS" ? <div><label className="mb-1 block text-xs font-medium text-slate-500">Meja <span className="text-red-500">*</span></label><input className={input} value={tableNumber} onChange={(e) => setTableNumber(e.target.value)} placeholder="Contoh: M-01 / 12" /></div> : <div className="rounded-md border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">Invoice langsung tidak memerlukan meja.</div>}
        </div>
      </Card>
      {recovery.failed && <p className="text-xs text-amber-700">Browser storage is unavailable. Save Draft before leaving this page.</p>}
      {queueNumber && <Card className="flex items-center justify-between border-emerald-200 bg-emerald-50 p-4"><div><div className="text-xs uppercase tracking-wide text-emerald-700">{transactionType === "POS" ? "Nomor Antrian" : "Nomor Invoice"}</div><div className="mt-1 text-2xl font-bold text-emerald-800">{queueNumber}</div></div>{transactionType === "POS" && <Badge variant="success">Meja {tableNumber}</Badge>}</Card>}

      <div className="grid gap-4 lg:grid-cols-[1fr_390px]">
        <Card className="p-4">
          <input className={`${input} mb-3`} placeholder="Cari menu, kode atau kategori" value={search} onChange={(e) => setSearch(e.target.value)} />
          {groups.length > 0 && <div className="mb-3 flex flex-wrap gap-1.5"><button type="button" onClick={() => setGroupFilter("")} className={`rounded-full px-3 py-1 text-xs font-medium ${!groupFilter ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600"}`}>All</button>{groups.map((g) => <button key={g} type="button" onClick={() => setGroupFilter(g)} className={`rounded-full px-3 py-1 text-xs font-medium ${groupFilter === g ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600"}`}>{g}</button>)}</div>}
          {productsQuery.isError && <p className="text-sm text-red-600">Could not load SELL items. Refresh and check your sales location.</p>}
          {!productsQuery.isLoading && !productsQuery.isError && products.length === 0 && <p className="p-4 text-sm text-slate-500">No SELL items available. Register menus and selling prices in Sell Item Master for this location / outlet.</p>}
          {productsQuery.isLoading ? <Loading /> : <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">{visibleProducts.map((product) => <button key={product.product_id} type="button" disabled={!product.sale_available} onClick={() => addToCart(product)} className="flex h-24 flex-col justify-between rounded-lg border border-slate-200 p-2.5 text-left hover:border-[#0F6758] disabled:opacity-40"><div><div className="line-clamp-2 text-xs font-semibold">{product.product_name}</div><div className="text-[10px] text-slate-400">{!product.sale_available ? (Number(product.selling_price) <= 0 ? "Set selling price" : (product.unavailable_reason || "Tax posting pending")) : product.group_name || product.product_code}</div></div><div className="flex items-center justify-between"><span className="text-sm font-bold text-[#0F6758]">{money(product.selling_price)}</span><span className="text-[10px] text-slate-500">{product.uom}</span></div></button>)}</div>}
        </Card>
        <Card className="h-fit p-4">
          <div className="mb-3 flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-semibold"><ShoppingCart className="h-4 w-4 text-[#0F6758]" />Order</div>{cart.length > 0 && <button type="button" onClick={clear} className="text-xs text-slate-500">Clear</button>}</div>
          {cart.length > 0 && <div className="mb-3 space-y-2">
            {(pendingDraftId || cart.some(line => line.sales_location_id)) ? <div className="text-xs text-slate-600">Sales location: <strong>{locations.find((l: any) => l.id === saleLocationId)?.name || "Item Master location"}</strong></div> : <SearchableSelect label="Order sales location" value={saleLocationId} options={locations} placeholder="Choose order location" onChange={value => { setOrderLocationId(value); setOrderDepartmentId(undefined); setRevenueAccountId(undefined); }} />}
            {(pendingDraftId || cart.some(line => line.department_id)) ? <div className="text-xs text-slate-600">Department / outlet: <strong>{orderDepartments.find((d: any) => d.id === saleDepartmentId)?.name || "Item Master department"}</strong></div> : <SearchableSelect label="Order department / outlet" value={saleDepartmentId} options={orderDepartments} placeholder="Choose order department" onChange={setOrderDepartmentId} />}
            <SearchableSelect label="Revenue account" required value={revenueAccountId} options={revenueAccounts} placeholder="Choose revenue account" onChange={setRevenueAccountId} />
          </div>}
          <div className="space-y-2">{cart.length === 0 && <div className="rounded-md border border-dashed p-6 text-center text-xs text-slate-500">Pilih menu untuk memulai.</div>}{cart.map((line) => <div key={line.product_id} className="rounded-md border p-2"><div className="flex justify-between gap-2"><div className="min-w-0"><div className="truncate text-xs font-semibold">{line.product_name}</div><div className="text-[10px] text-slate-400">{money(line.unit_price)} / {line.uom}</div></div><button type="button" onClick={() => changeQty(line.product_id, -line.quantity)} className="text-slate-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></button></div><div className="mt-2 flex items-center justify-between"><div className="flex items-center gap-1"><button type="button" onClick={() => changeQty(line.product_id, -1)} className="grid h-7 w-7 place-items-center rounded border"><Minus className="h-3.5 w-3.5" /></button><span className="w-8 text-center text-sm">{line.quantity}</span><button type="button" onClick={() => changeQty(line.product_id, 1)} className="grid h-7 w-7 place-items-center rounded border"><Plus className="h-3.5 w-3.5" /></button></div><span className="text-sm font-semibold">{money(line.quantity * line.unit_price)}</span></div></div>)}</div>
          <div className="mt-4 space-y-2 border-t pt-3 text-sm"><div className="flex justify-between"><span>Subtotal</span><span>{money(subtotal)}</span></div><div className="flex items-center justify-between"><span>Discount</span><input className="h-9 w-32 rounded border px-2 text-right" type="number" min={0} value={discount} onChange={(e) => setDiscount(e.target.value)} /></div><div className="flex justify-between"><span>Service charge</span><span>{money(serviceCharge)}</span></div><div className="flex justify-between"><span>{taxLabel}</span><span>{money(tax)}</span></div><div className="flex justify-between border-t pt-2 text-base font-bold"><span>Total</span><span>{money(total)}</span></div></div>
          <div className="mt-4 space-y-2"><select className={input} value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PosPaymentMethod)}><option value="CASH">Cash</option><option value="CARD">Card</option><option value="BANK_TRANSFER">Bank Transfer</option></select>{paymentMethod === "CASH" && <><input className={input} type="number" min={0} placeholder="Cash received" value={amountReceived} onChange={(e) => setAmountReceived(e.target.value)} /><div className="flex justify-between text-xs text-slate-500"><span>Change</span><span>{money(change)}</span></div></>}</div>
          {error && <div className="mt-3 rounded-md bg-red-50 p-2 text-xs text-red-700">{error}</div>}
          {lastNumber && <div className="mt-3 rounded-md bg-emerald-50 p-2 text-xs text-emerald-700">Saved: <strong>{lastNumber}</strong></div>}
          <div className="mt-4 grid grid-cols-2 gap-2"><Button variant="outline" disabled={!cart.length || saveDraft.isPending || createAndPost.isPending} onClick={() => saveDraft.mutate()}>Save Draft</Button><Button variant="primary" disabled={!cart.length || createAndPost.isPending || saveDraft.isPending} onClick={checkout}><Receipt className="h-4 w-4" /> {transactionType === "POS" ? "Ambil Nomor & Bayar" : "Create Invoice"}</Button></div>
        </Card>
      </div>
    </div>
  );
}

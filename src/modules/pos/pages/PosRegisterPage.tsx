import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Banknote, Boxes, CheckCircle2, CreditCard, Landmark, Minus, Plus, Printer, ShoppingCart, Trash2 } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import { DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";
import { posApi, type PosItemIn, type PosPaymentMethod } from "../api";
import { warehouseApi } from "@/modules/master/warehouses/api/warehouseApi";

const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

interface CartLine {
  product_id: number;
  product_code: string;
  product_name: string;
  group_name: string;
  uom: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  is_taxable: boolean;
  stock: number;
}

export default function PosRegisterPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const canSell = canAccess(user, POS_ROLES, "pos.sell");

  const [warehouseId, setWarehouseId] = useState<number | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [discount, setDiscount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PosPaymentMethod>("CASH");
  const [amountReceived, setAmountReceived] = useState("");
  const [formError, setFormError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [receipt, setReceipt] = useState<any | null>(null);

  const warehousesQuery = useQuery({
    queryKey: ["pos-warehouses"],
    queryFn: async () => (await warehouseApi.list()).data,
  });
  const warehouses: any[] = warehousesQuery.data ?? [];
  const warehouseOptions = warehouses.map((w) => ({ id: w.id, code: w.code, name: w.name }));
  useEffect(() => {
    if (!warehouseId && warehouses.length > 0) setWarehouseId(warehouses[0].id);
  }, [warehouses]); // eslint-disable-line react-hooks/exhaustive-deps

  const productsQuery = useQuery({
    queryKey: ["pos-products", warehouseId, search],
    queryFn: async () => (await posApi.products({ warehouse_id: warehouseId, search: search.trim() || undefined, page: 1, page_size: 200 })).data,
    enabled: Boolean(warehouseId),
  });
  const products: any[] = useMemo(() => productsQuery.data?.items ?? [], [productsQuery.data]);
  const groups = useMemo(() => Array.from(new Set(products.map((p: any) => p.group_name).filter(Boolean))) as string[], [products]);
  const visibleProducts = useMemo(
    () => (groupFilter ? products.filter((p: any) => p.group_name === groupFilter) : products),
    [products, groupFilter],
  );

  const inCart = (productId: number) => cart.find((line) => line.product_id === productId);
  const addToCart = (product: any) => {
    setFormError("");
    const existing = inCart(product.product_id);
    if (existing) {
      setCart((current) => current.map((line) => (line.product_id === product.product_id ? { ...line, quantity: line.quantity + 1 } : line)));
    } else {
      setCart((current) => [...current, {
        product_id: product.product_id,
        product_code: product.product_code,
        product_name: product.product_name,
        group_name: product.group_name,
        uom: product.uom,
        quantity: 1,
        unit_price: Number(product.selling_price ?? 0),
        tax_rate: Number(product.tax_rate ?? 0),
        is_taxable: Boolean(product.is_taxable),
        stock: Number(product.quantity ?? 0),
      }]);
    }
  };
  const changeQty = (productId: number, delta: number) => {
    setCart((current) => current
      .map((line) => (line.product_id === productId ? { ...line, quantity: Math.max(0, line.quantity + delta) } : line))
      .filter((line) => line.quantity > 0));
  };
  const removeLine = (productId: number) => setCart((current) => current.filter((line) => line.product_id !== productId));
  const clearCart = () => {
    setCart([]);
    setDiscount("");
    setPaymentMethod("CASH");
    setAmountReceived("");
  };

  const subtotal = cart.reduce((sum, line) => sum + line.quantity * line.unit_price, 0);
  const tax = cart.reduce((sum, line) => sum + (line.is_taxable && line.tax_rate > 0 ? line.quantity * line.unit_price * line.tax_rate / 100 : 0), 0);
  const discountValue = Math.min(Number(discount) || 0, subtotal);
  const total = subtotal - discountValue + tax;
  const change = paymentMethod === "CASH" ? Math.max((Number(amountReceived) || 0) - total, 0) : 0;

  const buildItems = (): PosItemIn[] => cart.map((line) => ({ product_id: line.product_id, quantity: line.quantity }));

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const created = (await posApi.create({ warehouse_id: warehouseId!, sale_date: new Date().toISOString().slice(0, 10), items: buildItems() })).data;
      return (await posApi.post(created.id, {
        payment_method: paymentMethod,
        payment_received: paymentMethod === "CASH" ? Number(amountReceived) : total,
        discount_amount: discountValue > 0 ? discountValue : null,
      })).data;
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["pos-products"] });
      setReceipt(data);
      setProcessing(false);
      clearCart();
    },
    onError: (error: any) => {
      setProcessing(false);
      setFormError(error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || "Checkout failed");
    },
  });

  const draftMutation = useMutation({
    mutationFn: async () => (await posApi.create({ warehouse_id: warehouseId!, sale_date: new Date().toISOString().slice(0, 10), items: buildItems() })).data,
    onSuccess: () => navigate("/pos/sales"),
    onError: (error: any) => setFormError(error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || "Save draft failed"),
  });

  const handleCheckout = () => {
    setFormError("");
    if (!warehouseId) return setFormError("Select a warehouse to sell from.");
    if (cart.length === 0) return setFormError("Add at least one item to the cart.");
    if (paymentMethod === "CASH" && (!Number(amountReceived) || Number(amountReceived) < total)) {
      return setFormError("Cash received must cover the total.");
    }
    setFormError("");
    setProcessing(true);
    checkoutMutation.mutate();
  };

  const handleSaveDraft = () => {
    setFormError("");
    if (!warehouseId) return setFormError("Select a warehouse to sell from.");
    if (cart.length === 0) return setFormError("Add at least one item to the cart.");
    setFormError("");
    draftMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Point of Sales" description="Sell items from warehouse stock, record payments and automatically post the sale to inventory and the general ledger." />

      <div className="grid gap-4 lg:grid-cols-[1fr_390px]">
        <Card className="p-4">
          <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center">
            <div className="w-full md:w-72"><SearchableSelect label="Warehouse" required value={warehouseId} options={warehouseOptions} placeholder="Select warehouse" onChange={(value) => setWarehouseId(value)} /></div>
            <div className="flex-1"><label className="mb-1 block text-xs font-medium text-slate-500">Search
              <input className={input} placeholder="Search item, code or category" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label></div>
          </div>
          {groups.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              <button type="button" onClick={() => setGroupFilter("")} className={`rounded-full px-3 py-1 text-xs font-medium ${groupFilter === "" ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>All</button>
              {groups.map((group) => (
                <button key={group} type="button" onClick={() => setGroupFilter(group)} className={`rounded-full px-3 py-1 text-xs font-medium ${groupFilter === group ? "bg-[#0F6758] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{group}</button>
              ))}
            </div>
          )}
          {productsQuery.isLoading ? <Loading /> : (
            <>
              {visibleProducts.length === 0 && <div className="rounded-md border border-dashed border-slate-300 p-8 text-center text-xs text-slate-500">No products with stock found for this warehouse.</div>}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
                {visibleProducts.map((product) => {
                  const inCartQty = inCart(product.product_id)?.quantity ?? 0;
                  const disabled = Number(product.quantity ?? 0) <= 0;
                  return (
                    <button key={product.product_id} type="button" disabled={disabled} onClick={() => addToCart(product)}
                      className="group flex h-24 flex-col justify-between rounded-lg border border-slate-200 bg-white p-2.5 text-left hover:border-[#0F6758] hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-45">
                      <div>
                        <div className="flex items-start justify-between gap-1">
                          <span className="line-clamp-2 text-xs font-medium text-slate-700">{product.product_name}</span>
                          <span className="shrink-0 text-[10px] text-slate-400">{product.product_code}</span>
                        </div>
                        <div className="text-[10px] text-slate-400">{product.group_name}{product.subgroup_name ? ` · ${product.subgroup_name}` : ""}</div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-[#0F6758]">{money(product.selling_price)}</span>
                        <div className="flex items-center gap-1">
                          {inCartQty > 0 && <Badge variant="success" className="!px-1.5">{inCartQty}</Badge>}
                          <span className={`px-1.5 text-[10px] ${Number(product.quantity) > 0 ? "text-slate-500" : "text-red-500"}`}>{num(product.quantity)} {product.uom}</span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </Card>

        <Card className="flex h-fit flex-col p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700"><ShoppingCart className="h-4 w-4 text-[#0F6758]" />Current Sale</div>
            {cart.length > 0 && <button type="button" onClick={clearCart} className="text-xs text-slate-500 hover:text-red-600">Clear</button>}
          </div>

          <div className="min-h-[120px] space-y-2">
            {cart.length === 0 && <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">Tap items on the left to start a sale.</div>}
            {cart.map((line) => (
              <div key={line.product_id} className="rounded-md border border-slate-200 p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-slate-700">{line.product_name}</div>
                    <div className="text-[10px] text-slate-400">{line.product_code} · {money(line.unit_price)}{line.is_taxable && line.tax_rate > 0 ? ` · PPN ${line.tax_rate}%` : ""}</div>
                  </div>
                  <button type="button" onClick={() => removeLine(line.product_id)} className="grid h-6 w-6 shrink-0 place-items-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    <button type="button" onClick={() => changeQty(line.product_id, -1)} className="grid h-7 w-7 place-items-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50"><Minus className="h-3.5 w-3.5" /></button>
                    <span className="w-10 text-center text-sm font-semibold tabular-nums">{num(line.quantity)}</span>
                    <button type="button" onClick={() => changeQty(line.product_id, 1)} disabled={line.quantity >= line.stock} className="grid h-7 w-7 place-items-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"><Plus className="h-3.5 w-3.5" /></button>
                  </div>
                  <span className="text-sm font-semibold tabular-nums">{money(line.quantity * line.unit_price)}</span>
                </div>
                {line.quantity >= line.stock && <div className="mt-1 text-[10px] text-red-500">Only {num(line.stock)} {line.uom} on hand</div>}
              </div>
            ))}
          </div>

          <div className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-sm">
            <div className="flex justify-between text-slate-600"><span>Subtotal</span><span className="tabular-nums">{money(subtotal)}</span></div>
            <div className="flex items-center justify-between text-slate-600">
              <span>Discount</span>
              <input type="number" min={0} placeholder="0" className="h-8 w-28 rounded-md border border-slate-300 px-2 text-right text-sm" value={discount} onChange={(e) => setDiscount(e.target.value)} />
            </div>
            <div className="flex justify-between text-slate-600"><span>PPN</span><span className="tabular-nums">{money(tax)}</span></div>
            <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-bold text-slate-800"><span>Total</span><span className="tabular-nums">{money(total)}</span></div>
          </div>

          <div className="mt-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Payment</div>
            <div className="grid grid-cols-3 gap-2">
              {([["CASH", "Cash", Banknote], ["CARD", "Card", CreditCard], ["BANK_TRANSFER", "Transfer", Landmark]] as const).map(([method, label, Icon]) => (
                <button key={method} type="button" onClick={() => { setPaymentMethod(method); setFormError(""); }} className={`flex flex-col items-center gap-1 rounded-md border px-2 py-2 text-xs font-medium ${paymentMethod === method ? "border-[#0F6758] bg-emerald-50 text-[#0F6758]" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}><Icon className="h-4 w-4" />{label}</button>
              ))}
            </div>
            {paymentMethod === "CASH" && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-slate-500">Cash Received</span>
                  <input type="number" min={0} className={input} placeholder="0" value={amountReceived} onChange={(e) => setAmountReceived(e.target.value)} />
                </label>
                <div><div className="mb-1 block text-xs font-medium text-slate-500">Change</div><div className="flex h-10 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-emerald-700 tabular-nums">{money(change)}</div></div>
              </div>
            )}
          </div>

          {formError && <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</div>}

          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={handleSaveDraft} loading={draftMutation.isPending}><Boxes className="h-4 w-4" />Save Draft</Button>
            <Button variant="success" onClick={handleCheckout} loading={processing} disabled={!canSell || processing}><CheckCircle2 className="h-4 w-4" />Checkout</Button>
          </div>
          {!canSell && <div className="mt-2 text-xs text-slate-500">You need the Point of Sales sell permission to complete sales.</div>}
        </Card>
      </div>

      <Dialog open={receipt !== null} onOpenChange={(open: boolean) => { if (!open) setReceipt(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-emerald-600" />Sale completed</DialogTitle></DialogHeader>
          <DialogBody>
            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-center">
                <div className="text-xs uppercase tracking-wide text-emerald-700">Transaction</div>
                <div className="text-lg font-bold text-emerald-800">{receipt?.transaction_number}</div>
                {(receipt?.payment_method === "CASH" && Number(receipt?.change_amount) > 0) && <div className="mt-1 text-sm text-emerald-700">Change due: <span className="font-bold">{money(receipt?.change_amount)}</span></div>}
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><div className="text-xs uppercase tracking-wide text-slate-500">Total</div><span className="font-bold">{money(receipt?.total_amount)}</span></div>
                <div><div className="text-xs uppercase tracking-wide text-slate-500">Payment</div>{receipt?.payment_method === "BANK_TRANSFER" ? "Bank Transfer" : receipt?.payment_method === "CARD" ? "Card" : "Cash"}</div>
                <div><div className="text-xs uppercase tracking-wide text-slate-500">Items</div>{num((receipt?.items ?? []).length)} line(s)</div>
                <div><div className="text-xs uppercase tracking-wide text-slate-500">Journal</div>{receipt?.journal_number || "-"}</div>
              </div>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => navigate("/pos/sales")}>View Sales</Button>
            <Button variant="primary" onClick={() => window.open(`/pos/sales/${receipt?.id}/print`, "_blank")}><Printer className="h-4 w-4" />Print Receipt</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
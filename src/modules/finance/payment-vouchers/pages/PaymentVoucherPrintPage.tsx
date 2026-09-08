import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getVoucherPrint } from "../api";
import useAuthStore from "@/store/auth";

const money = (v: unknown) => Number(v || 0).toLocaleString("id-ID", { minimumFractionDigits: 2 });

export default function PaymentVoucherPrintPage() {
  const { id } = useParams();
  const voucherId = Number(id);
  const user = useAuthStore((s) => s.user);
  const q = useQuery({ queryKey: ["payment-voucher-print", voucherId], queryFn: async () => (await getVoucherPrint(voucherId)).data });

  if (q.isLoading) return <div className="py-16 text-center">Loading print...</div>;
  if (q.isError) return <div className="py-16 text-center text-red-600">Failed to load.</div>;
  const v: any = q.data;

  return (
    <div className="print-document mx-auto max-w-[1100px] space-y-4 bg-white p-6 text-sm">
      <div className="flex items-start justify-between border-b pb-4">
        <div><h1 className="text-2xl font-bold">MMH-Connect</h1><h2 className="text-lg font-semibold">Payment Voucher — {v.voucher_number}</h2><p className="text-xs text-slate-500">{v.location_name} • {v.voucher_date} • Periode {v.period_from || "—"} → {v.period_to || "—"}</p></div>
        <div className="text-right text-xs"><div>Printed by {user?.full_name || user?.username} • {new Date().toLocaleString()}</div><div className="mt-1 font-mono">PV-{v.id}</div></div>
      </div>
      <div className="rounded border">
        <div className="bg-[#0B3D2E] px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white">PEMBAYARAN SUPPLIER — {v.location_name}</div>
        <table className="w-full text-xs">
          <thead><tr className="bg-slate-100"><th className="border p-2 text-left">NO</th><th className="border p-2 text-left">DESKRIPSI</th><th className="border p-2">PERIODE</th><th className="border p-2">UNIT</th><th className="border p-2 text-left">NAMA SUPPLIER</th><th className="border p-2 text-right">TOTAL TAGIHAN</th><th className="border p-2">NAMA BANK</th><th className="border p-2">NO REK</th><th className="border p-2">PENERIMA</th></tr></thead>
          <tbody>
            {v.groups?.map((g: any, idx: number) => (
              <tr key={g.supplier_id}>
                <td className="border p-2 text-center">{idx + 1}</td>
                <td className="border p-2">BAYAR {g.supplier_name}</td>
                <td className="border p-2 text-center">{v.period_from || v.voucher_date} — {v.period_to || v.voucher_date}</td>
                <td className="border p-2 text-center">{v.location_name}</td>
                <td className="border p-2">{g.supplier_name}</td>
                <td className="border p-2 text-right tabular-nums">{money(g.total)}</td>
                <td className="border p-2">{g.bank?.bank_name || "—"}</td>
                <td className="border p-2 font-mono">{g.bank?.account_number || "—"}</td>
                <td className="border p-2">{g.bank?.account_name || g.supplier_name}</td>
              </tr>
            ))}
            <tr className="bg-slate-100 font-bold"><td colSpan={5} className="border p-2 text-right">TOTAL</td><td className="border p-2 text-right">{money(v.total_amount)}</td><td colSpan={3} className="border p-2"></td></tr>
          </tbody>
        </table>
      </div>
      <div className="grid grid-cols-5 gap-4 pt-8 text-center text-xs">
        <div><div className="h-16"></div><div className="border-t pt-2">Prepared by<br />Purchasing</div></div>
        <div><div className="h-16"></div><div className="border-t pt-2">Verificator by<br />Accounting</div></div>
        <div><div className="h-16"></div><div className="border-t pt-2">Acknowledged by<br />General Manager</div></div>
        <div><div className="h-16"></div><div className="border-t pt-2">Approved by<br />Financial Controller</div></div>
        <div><div className="h-16"></div><div className="border-t pt-2">Approved by<br />Direktur Utama</div></div>
      </div>
      <div className="flex justify-end gap-2 print:hidden"><button onClick={() => window.print()} className="rounded bg-emerald-700 px-4 py-2 text-white">Print</button></div>
      <div className="text-[10px] text-slate-500">Voucher {v.voucher_number} • {v.status} • {v.groups?.length} supplier(s), {v.allocations?.length} invoice(s)</div>
    </div>
  );
}

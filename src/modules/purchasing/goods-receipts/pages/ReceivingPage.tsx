import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import ListToolbar from "@/components/common/ListToolbar";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import ReceiveGoodsDialog from "../components/ReceiveGoodsDialog";
import { useAllGoodsReceipts, useReceivablePurchaseOrders } from "../hooks/useGoodsReceipts";
import useAuthorization from "@/hooks/useAuthorization";

export default function ReceivingPage() {
  const navigate = useNavigate();
  const { canPerform } = useAuthorization();
  const canCreate = canPerform("receive", ["WAREHOUSE", "PURCHASING"]);
  const [search, setSearch] = useState(""), [destination, setDestination] = useState("ALL"), [advanced, setAdvanced] = useState(false), [creating, setCreating] = useState(false);
  const query = useAllGoodsReceipts();
  const pending = useReceivablePurchaseOrders();
  const data = query.data ?? [];
  const rows = useMemo(() => { const term = search.trim().toLowerCase(); return data.filter((receipt) => (destination === "ALL" || receipt.destination_type === destination) && (!term || [receipt.receipt_number, receipt.purchase_order_number, receipt.supplier_name, receipt.received_by_name, receipt.warehouse_name].filter(Boolean).join(" ").toLowerCase().includes(term))); }, [data, search, destination]);
  const destinationSelect = <select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={destination} onChange={(event) => setDestination(event.target.value)}><option value="ALL">All destinations</option><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select>;
  return <><div className="space-y-6"><PageHeader title="Receiving" description="Receive approved purchase orders into warehouse stock or direct use." actions={canCreate ? <Button onClick={() => setCreating(true)}><Plus size={16}/> Create Receiving</Button> : undefined}/>
    <ModuleSummary metrics={[{label:"Receivable POs",value:(pending.data ?? []).length},{label:"Receipts",value:data.length},{label:"Warehouse",value:data.filter((row) => row.destination_type === "WAREHOUSE").length},{label:"Direct Use",value:data.filter((row) => row.destination_type === "DIRECT_USE").length}]}/>
    <Card className="overflow-hidden p-0"><div className="p-5"><ListToolbar search={search} searchPlaceholder="Search receipt, PO, supplier, receiver, or warehouse..." onSearch={setSearch} filters={destinationSelect} advancedOpen={advanced} onAdvancedToggle={() => setAdvanced(!advanced)} advancedFilters={<div className="max-w-xs">{destinationSelect}</div>} onRefresh={() => {query.refetch(); pending.refetch();}} footer={<div className="text-xs text-slate-500">Showing {rows.length} receiving document{rows.length === 1 ? "" : "s"}</div>}/></div>
      {query.isLoading ? <div className="py-12"><Loading/></div> : query.isError ? <div role="alert" className="m-5 rounded border border-red-200 bg-red-50 p-4 text-red-700">Receiving documents could not be loaded.</div> : <div className="overflow-x-auto"><table className="min-w-[1200px] w-full text-sm"><thead><tr className="border-b bg-slate-50 text-left"><th className="p-3">Receipt Number</th><th>PO Number</th><th>Supplier</th><th>Receipt Date</th><th>Destination Type</th><th>Warehouse</th><th>Received By</th><th>Status</th><th className="p-3 text-right">Action</th></tr></thead><tbody>{rows.map((receipt) => <tr key={receipt.id} className="border-b hover:bg-slate-50"><td className="p-3 font-medium">{receipt.receipt_number}</td><td>{receipt.purchase_order_number}</td><td>{receipt.supplier_name ?? "—"}</td><td>{new Date(receipt.received_at).toLocaleDateString()}</td><td>{receipt.destination_type === "WAREHOUSE" ? "Warehouse" : "Direct Use"}</td><td>{receipt.destination_type === "WAREHOUSE" ? receipt.warehouse_name ?? "—" : "—"}</td><td>{receipt.received_by_name ?? "—"}</td><td>{receipt.status}</td><td className="p-3 text-right"><Button size="sm" variant="outline" onClick={() => navigate(`/receiving/${receipt.id}`)}>View</Button></td></tr>)}{!rows.length && <tr><td colSpan={9} className="p-10 text-center text-slate-500">No receiving documents found.</td></tr>}</tbody></table></div>}
    </Card></div>{canCreate && <ReceiveGoodsDialog open={creating} purchaseOrder={null} onClose={() => setCreating(false)}/>}</>;
}

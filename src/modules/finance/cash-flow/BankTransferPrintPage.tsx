import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import { getTransfer } from "./api";

export default function BankTransferPrintPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["bank-transfer", id, "print"], queryFn: () => getTransfer(Number(id)), enabled: !!id });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Transfer could not be loaded.</p>;
  const transfer = query.data;
  return <article className="mx-auto max-w-[210mm] bg-white p-8 text-black">
    <div className="mb-6 flex justify-end print:hidden"><Button onClick={() => window.print()}>Print</Button></div>
    <header className="mb-8 flex justify-between border-b-2 border-black pb-5"><div><h1 className="text-2xl font-bold">HMM-Connect</h1><div>Hotel Mutiara Merdeka</div></div><div className="text-right"><h2 className="text-2xl font-bold">BANK TRANSFER</h2><div>{transfer.transfer_number}</div></div></header>
    <div className="grid grid-cols-2 gap-4"><div>Date: {transfer.transfer_date}</div><div>Status: {transfer.status}</div><div>Source: {transfer.source_account_code} — {transfer.source_account_name}</div><div>Destination: {transfer.destination_account_code} — {transfer.destination_account_name}</div><div>Amount: {Number(transfer.amount).toLocaleString()} {transfer.currency}</div><div>Reference: {transfer.reference_number || "—"}</div><div className="col-span-2">Notes: {transfer.notes || "—"}</div><div>Journal: {transfer.journal_number || "—"}</div></div>
  </article>;
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {Calculator, FileBarChart, FolderTree, Plus, Printer} from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import { listAssets } from "./api";

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const PAGE_SIZE = 20;

export default function FixedAssetListPage() {
  const [page, setPage] = useState(1);
  const assets = useQuery({
    queryKey: ["fixed-assets", page],
    queryFn: () => listAssets({ page, page_size: PAGE_SIZE }),
    placeholderData: (previousData) => previousData,
  });
  const rows = assets.data?.items ?? [];
  const total = assets.data?.total_items ?? 0;
  const pages = Math.max(assets.data?.total_pages ?? 0, 1);

  return <div className="space-y-5">
    <PageHeader
      title="Fixed Assets"
      description="Manage tangible assets, depreciation, and amortizable costs from one finance workspace."
      actions={<>
<Link to="/fixed-assets/new"><Button><Plus size={16}/> New Fixed Asset</Button></Link>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}
    />

    <div className="grid gap-3 md:grid-cols-4">
      <Link to="/asset-categories"><Card className="h-full p-4 hover:border-emerald-300"><FolderTree className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Asset Categories</div><div className="mt-1 text-xs text-slate-500">Accounts and useful-life defaults</div></Card></Link>
      <Link to="/depreciation-runs"><Card className="h-full p-4 hover:border-emerald-300"><Calculator className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Depreciation Runs</div><div className="mt-1 text-xs text-slate-500">Calculate and post tangible-asset depreciation</div></Card></Link>
      <Link to="/fixed-assets/amortization"><Card className="h-full p-4 hover:border-emerald-300"><Calculator className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Amortization</div><div className="mt-1 text-xs text-slate-500">Intangible assets and amortizable costs</div></Card></Link>
      <Link to="/reports/fixed-assets"><Card className="h-full p-4 hover:border-emerald-300"><FileBarChart className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Asset Reports</div><div className="mt-1 text-xs text-slate-500">Book value and depreciation reporting</div></Card></Link>
    </div>

    <Card className="overflow-x-auto p-0">
      <div className="border-b px-4 py-3 font-semibold">Asset Register</div>
      <Table className={`min-w-[900px] ${assets.isFetching ? "opacity-70" : ""}`} containerClassName="rounded-none border-0 shadow-none">
        <THead><TR className="whitespace-nowrap"><TH>Asset</TH><TH>Acquired</TH><TH numeric>Cost</TH><TH numeric>Accumulated Depreciation</TH><TH numeric>Net Book Value</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead>
        <TBody>{rows.map((asset: any) => <TR key={asset.id} className="whitespace-nowrap"><TD><TableCellStack primary={asset.asset_name} secondary={`${asset.asset_number} · ${asset.category}`}/></TD><TD>{asset.acquisition_date}</TD><TD numeric>{money(asset.acquisition_cost)}</TD><TD numeric>{money(asset.accumulated_depreciation)}</TD><TD numeric className="font-semibold">{money(asset.net_book_value)}</TD><TD><Badge>{asset.status}</Badge></TD><TD><div className="flex justify-end"><Link className={TABLE_UI.documentLink} to={`/fixed-assets/${asset.id}`}>View</Link></div></TD></TR>)}</TBody>
      </Table>
      {!assets.isLoading && !rows.length && <div className="p-10 text-center text-sm text-slate-500">No fixed assets registered.</div>}
      {!assets.isLoading && total > 0 && <div className="border-t px-4 py-3"><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="assets" onChange={setPage}/></div>}
    </Card>
  </div>;
}

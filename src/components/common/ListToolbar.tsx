import type { ReactNode } from "react";
import { Columns3, Download, Filter, RefreshCw, Search, SlidersHorizontal, Upload } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";

interface Props {
  search:string; searchPlaceholder?:string; onSearch:(value:string)=>void;
  filters?:ReactNode; advancedFilters?:ReactNode; advancedOpen?:boolean; onAdvancedToggle?:()=>void;
  onExport?:()=>void; onRefresh?:()=>void; onImport?:()=>void; columns?:ReactNode; footer?:ReactNode;
}

export default function ListToolbar({search, searchPlaceholder="Search...", onSearch, filters, advancedFilters, advancedOpen, onAdvancedToggle, onExport, onRefresh, onImport, columns, footer}:Props) {
  return <div className="space-y-4 border-b border-slate-200 pb-4">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <div className="relative min-w-0 flex-1 lg:max-w-md"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400"/><Input className="pl-9" type="search" value={search} placeholder={searchPlaceholder} onChange={(event) => onSearch(event.target.value)}/></div>
      <div className="flex flex-1 flex-wrap items-center gap-2">{filters}<Button size="sm" variant="outline" onClick={onAdvancedToggle}><SlidersHorizontal size={15}/> Advanced Filters</Button><Button size="sm" variant="outline" onClick={onExport}><Download size={15}/> Export</Button>{onImport && <Button size="sm" variant="outline" onClick={onImport}><Upload size={15}/> Import</Button>}<Button size="sm" variant="outline" onClick={onRefresh}><RefreshCw size={15}/> Refresh</Button>{columns ?? <Button size="sm" variant="outline" disabled title="Column preferences coming soon"><Columns3 size={15}/> Columns</Button>}</div>
    </div>
    {advancedOpen && advancedFilters && <div className="rounded-lg bg-slate-50 p-4"><div className="mb-3 flex items-center gap-2 text-sm font-medium"><Filter size={15}/> Advanced Filters</div>{advancedFilters}</div>}
    {footer}
  </div>;
}

import Button from "@/components/ui/Button";

interface PaginationProps {
  page: number;
  pages: number;
  onChange: (page: number) => void;
  total?: number;
  pageSize?: number;
  noun?: string;
}

export default function Pagination({ page, pages, onChange, total, pageSize, noun = "records" }: PaginationProps) {
  const safePages = Math.max(pages, 1);
  const start = total && pageSize ? Math.min((page - 1) * pageSize + 1, total) : undefined;
  const end = total && pageSize ? Math.min(page * pageSize, total) : undefined;

  return (
    <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-4 text-sm sm:flex-row sm:items-center sm:justify-between">
      <span className="text-slate-500">
        {typeof total === "number" && typeof start === "number" && typeof end === "number"
          ? total === 0 ? `0 ${noun}` : `Showing ${start}-${end} of ${total} ${noun}`
          : `Page ${page} of ${safePages}`}
      </span>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
        <span className="min-w-24 text-center">Page {page} of {safePages}</span>
        <Button size="sm" variant="outline" disabled={page >= safePages} onClick={() => onChange(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { Search, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import Dialog, { DialogContent, DialogTitle } from "@/components/ui/Dialog";
import { visibleNavigation } from "@/components/navigation/navigationConfig";
import useAuthStore from "@/store/auth";

type FeatureLink = { label: string; section: string; url: string };

export default function FeatureSearch() {
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(0);

  const links = useMemo<FeatureLink[]>(() => visibleNavigation(user).flatMap((group) => {
    if (group.url) return [{ label: group.title, section: "Main", url: group.url }];
    return (group.children ?? [])
      .filter((item) => item.url && !item.disabled)
      .map((item) => ({ label: item.title, section: group.title, url: item.url! }));
  }), [user]);

  const results = useMemo(() => {
    const words = search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const matches = links.filter((item) => {
      const text = `${item.label} ${item.section}`.toLocaleLowerCase();
      return words.every((word) => text.includes(word));
    });
    return matches.slice(0, 12);
  }, [links, search]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
    else {
      setSearch("");
      setSelected(0);
    }
  }, [open]);

  const goTo = (item: FeatureLink) => {
    setOpen(false);
    navigate(item.url);
  };

  return <>
    <button
      type="button"
      title="Search features (Ctrl+K)"
      aria-label="Search features"
      className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]"
      onClick={() => setOpen(true)}
    >
      <Search className="h-[18px] w-[18px]" />
    </button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="top-[20%] max-w-xl -translate-y-0">
        <DialogTitle className="sr-only">Search application features</DialogTitle>
        <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4 pr-12">
          <Search size={20} className="shrink-0 text-emerald-700" />
          <input
            ref={inputRef}
            aria-label="Search application menus"
            className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
            placeholder="Search menus, reports, and features..."
            value={search}
            onChange={(event) => { setSearch(event.target.value); setSelected(0); }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") { event.preventDefault(); setSelected((index) => Math.min(index + 1, results.length - 1)); }
              if (event.key === "ArrowUp") { event.preventDefault(); setSelected((index) => Math.max(0, index - 1)); }
              if (event.key === "Enter" && results[selected]) { event.preventDefault(); goTo(results[selected]); }
            }}
          />
        </div>
        <div className="max-h-[50vh] overflow-y-auto p-2" role="listbox" aria-label="Matching features">
          {results.length === 0 ? <p className="px-4 py-8 text-center text-sm text-slate-500">No matching feature found.</p> : results.map((item, index) => <button
            key={`${item.url}-${item.label}`}
            type="button"
            role="option"
            aria-selected={selected === index}
            className={`flex w-full items-center justify-between rounded-lg px-4 py-3 text-left text-sm transition ${selected === index ? "bg-emerald-50 text-emerald-900" : "text-slate-700 hover:bg-slate-50"}`}
            onMouseEnter={() => setSelected(index)}
            onClick={() => goTo(item)}
          >
            <span><span className="font-medium">{item.label}</span><span className="ml-2 text-xs text-slate-500">{item.section}</span></span>
            <ArrowRight size={15} className="shrink-0 text-slate-400" />
          </button>)}
        </div>
        <div className="border-t border-slate-100 px-5 py-2 text-xs text-slate-500">Use ↑ ↓ to select · Enter to open · Esc to close</div>
      </DialogContent>
    </Dialog>
  </>;
}

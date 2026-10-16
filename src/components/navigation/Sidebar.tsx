import { useEffect, useId, useRef, useState, type MouseEvent, type FocusEvent } from "react";
import { createPortal } from "react-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowLeft, X } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import useAuthStore from "@/store/auth";
import { activeNavigation, navigationIcon, visibleNavigation } from "./navigationConfig";

interface Props { open?: boolean; onClose?: () => void }

export default function Sidebar({ open = false, onClose }: Props) {
  const location = useLocation();
  const user = useAuthStore(state => state.user);
  const groups = visibleNavigation(user);
  const active = activeNavigation(groups, location.pathname, location.search);
  const [flyout, setFlyout] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ title: string; top: number } | null>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const tooltipId = useId();
  const selected = groups.find(group => group.title === flyout);
  const close = () => { setFlyout(null); setTooltip(null); onClose?.(); };
  const showTooltip = (title: string, target: HTMLElement) => {
    const bounds = target.getBoundingClientRect();
    setTooltip({ title, top: Math.max(20, Math.min(window.innerHeight - 20, bounds.top + bounds.height / 2)) });
  };
  useEffect(() => {
    setFlyout(null); setTooltip(null); onClose?.();
  }, [location.pathname, location.search, onClose]);
  useEffect(() => {
    const hide = () => setTooltip(null);
    window.addEventListener("resize", hide); window.addEventListener("scroll", hide, true);
    return () => { window.removeEventListener("resize", hide); window.removeEventListener("scroll", hide, true); };
  }, []);

  return <>
    <aside aria-label="Module navigation" className="module-icon-rail relative z-40 hidden h-screen w-16 shrink-0 flex-col border-r border-white/10 bg-[#103E36] text-white lg:flex">
      <Link to="/dashboard" aria-label="MMH dashboard" className="flex h-12 shrink-0 items-center justify-center border-b border-white/10 text-[11px] font-bold text-emerald-50/80">MMH</Link>
      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {groups.map(group => {
          const Icon = group.icon;
          const selectedGroup = active?.group.title === group.title || flyout === group.title;
          const className = `flex h-10 w-full items-center justify-center rounded-lg ${selectedGroup ? "bg-[#0F6758] text-white" : "text-emerald-50/75 hover:bg-white/10"}`;
          const tooltipProps = {
            "aria-describedby": tooltip?.title === group.title ? tooltipId : undefined,
            onMouseEnter: (event: MouseEvent<HTMLElement>) => showTooltip(group.title, event.currentTarget),
            onMouseLeave: () => setTooltip(null),
            onFocus: (event: FocusEvent<HTMLElement>) => showTooltip(group.title, event.currentTarget),
            onBlur: () => setTooltip(null),
          };
          return group.url ? <Link key={group.title} to={group.url} aria-label={group.title} aria-current={selectedGroup ? "page" : undefined} onClick={close} className={className} {...tooltipProps}><Icon size={20}/></Link>
            : <button key={group.title} type="button" aria-label={group.title} aria-haspopup="dialog" aria-expanded={flyout === group.title} onClick={event => { trigger.current = event.currentTarget; setTooltip(null); setFlyout(group.title); }} className={className} {...tooltipProps}><Icon size={20}/></button>;
        })}
      </nav>
    </aside>
    {tooltip && !selected && createPortal(<div id={tooltipId} role="tooltip" className="pointer-events-none fixed z-[100] hidden -translate-y-1/2 whitespace-nowrap rounded-md bg-[#103E36] px-3 py-2 text-xs font-medium text-white shadow-lg lg:block" style={{left:72,top:tooltip.top}}>{tooltip.title}</div>, document.body)}
    <Dialog.Root open={Boolean(selected) || open} onOpenChange={next => { if (!next) close(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/10"/>
        <Dialog.Content className="module-launcher" aria-describedby={undefined} onCloseAutoFocus={event => { event.preventDefault(); const target = trigger.current?.getClientRects().length ? trigger.current : document.querySelector<HTMLElement>('[aria-label="Open modules"]'); target?.focus(); }}>
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
            {selected && open && <button type="button" aria-label="All modules" className="rounded p-1 text-slate-500 hover:bg-slate-100" onClick={() => setFlyout(null)}><ArrowLeft size={16}/></button>}
            <Dialog.Title className="flex-1 text-sm font-semibold text-slate-800">{selected?.title ?? "Modules"}</Dialog.Title>
            <Dialog.Close className="rounded p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close module menu"><X size={17}/></Dialog.Close>
          </div>
          <nav aria-label={selected ? `${selected.title} submodules` : "Choose module"} className="module-launcher-grid">
            {selected ? selected.children?.map(child => {
              const Icon = navigationIcon(child);
              return child.disabled ? <span key={child.title} className="module-launcher-tile opacity-40"><Icon size={23}/><span>{child.title}</span></span> : <Link key={child.title} to={child.url!} onClick={close} className={`module-launcher-tile ${active?.child.url === child.url ? "is-active" : ""}`} aria-current={active?.child.url === child.url ? "page" : undefined}><Icon size={23}/><span>{child.title}</span></Link>;
            }) : groups.map(group => {
              const Icon = group.icon;
              return group.url ? <Link key={group.title} to={group.url} onClick={close} className="module-launcher-tile"><Icon size={23}/><span>{group.title}</span></Link> : <button key={group.title} type="button" className="module-launcher-tile" onClick={() => setFlyout(group.title)}><Icon size={23}/><span>{group.title}</span></button>;
            })}
          </nav>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </>;
}

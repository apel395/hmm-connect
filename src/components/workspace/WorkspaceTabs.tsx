import { useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, Layers, RotateCcw, X } from "lucide-react";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import WorkspaceBackButton from "./WorkspaceBackButton";
import useWorkspaceTabs from "@/store/workspaceTabs";
import useAuth from "@/store/auth";
import { activeNavigation, navigationIcon, visibleNavigation } from "@/components/navigation/navigationConfig";
import { workspaceTabGroup, workspaceTitle } from "./workspaceTitle";

export default function WorkspaceTabs() {
  const location = useLocation(), navigate = useNavigate(), client = useQueryClient();
  const user = useAuth(state => state.user);
  const active = activeNavigation(visibleNavigation(user), location.pathname, location.search);
  const currentPath = `${location.pathname}${location.search}`;
  const title = workspaceTitle(location.pathname, location.search);
  const { tabs, closedTabs, ensureTab, closeTab, closeOtherTabs, closeTabsToRight, closeAllTabs, reopenLastClosed } = useWorkspaceTabs();
  const [open, setOpen] = useState(false), [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null), linksRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => searchRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open]);
  const current = tabs.find(tab => tab.id === currentPath);
  const closable = tabs.some(tab => !tab.pinned);
  const activatedPath = useRef("");
  useEffect(() => {
    if (activatedPath.current === location.pathname) return;
    activatedPath.current = location.pathname;
    void client.invalidateQueries({refetchType:"active"});
  }, [client, location.pathname]);
  useEffect(() => {
    if (location.pathname === "/" || location.pathname.endsWith("/print")) return;
    ensureTab({ id:currentPath, path:currentPath, title, pinned:location.pathname === "/dashboard", group:workspaceTabGroup(location.pathname, location.search) });
    document.title = `${title} · MMH-Connect`;
    setOpen(false);
    linksRef.current?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView({block:"nearest",inline:"nearest"});
  }, [currentPath, ensureTab, location.pathname, location.search, title]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || !event.shiftKey || event.key.toLowerCase() !== "t") return;
      const path = reopenLastClosed();
      if (path) { event.preventDefault(); navigate(path); }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [navigate, reopenLastClosed]);
  const close = (id: string) => {
    const result = closeTab(id);
    if (id === currentPath && result.nextPath) navigate(result.nextPath);
  };
  const reopen = () => { const path = reopenLastClosed(); if (path) navigate(path); };
  const visible = tabs.filter(tab => `${tab.title} ${tab.path}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <div className="mmh-workspace-tabs module-topbar print:hidden">
    <WorkspaceBackButton/>
    {active?.group.children ? <>
      <Dropdown.Root>
        <Dropdown.Trigger className="module-top-picker" aria-label={`${active.group.title} modules`} title={`${active.group.title} modules`}><active.group.icon size={15}/><span>{active.group.title}</span><ChevronDown size={13}/></Dropdown.Trigger>
        <Dropdown.Portal><Dropdown.Content align="start" sideOffset={6} className="module-top-popup" aria-label={`${active.group.title} modules`}>
          <Dropdown.Label className="px-3 pt-3 text-xs font-semibold text-slate-500">{active.group.title}</Dropdown.Label>
          <div className="module-launcher-grid">{active.group.children.filter(child=>!child.disabled).map(child=>{const Icon=navigationIcon(child);return <Dropdown.Item key={child.title} asChild><Link to={child.url!} className={`module-launcher-tile ${active.child.url===child.url ? "is-active" : ""}`}><Icon size={22}/><span>{child.title}</span></Link></Dropdown.Item>;})}</div>
        </Dropdown.Content></Dropdown.Portal>
      </Dropdown.Root>
      <nav ref={linksRef} className="module-top-links" aria-label={`${active.group.title} menus`}>{active.group.children.filter(child=>!child.disabled).map(child=><Link key={child.title} to={child.url!} title={child.title} aria-current={active.child.url===child.url?"page":undefined}>{child.title}</Link>)}</nav>
    </> : <span className="module-top-current" title={title}>{title}</span>}
    <div className="module-tab-controls">
      <Dropdown.Root open={open} onOpenChange={next=>{setOpen(next);if(!next)setSearch("");}}>
        <Dropdown.Trigger className="open-tabs-trigger" aria-label={`Open tabs (${tabs.length})`} title="Open documents and workspaces"><Layers size={15}/><span>Open tabs</span><b>{tabs.length}</b><ChevronDown size={12}/></Dropdown.Trigger>
        <Dropdown.Portal><Dropdown.Content align="end" sideOffset={6} className="open-tabs-popup" aria-label="Open tabs">
          <div className="border-b border-slate-100 p-2"><input ref={searchRef} data-form-control aria-label="Find open tab" placeholder="Find a document or module…" value={search} onChange={event=>setSearch(event.target.value)} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();event.stopPropagation();event.currentTarget.closest('[role="menu"]')?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();}else if(event.key!=='Escape')event.stopPropagation();}} className="h-8 w-full rounded border border-slate-200 px-2 text-xs outline-none focus:border-emerald-600"/></div>
          <div className="open-tabs-list">{visible.map(tab=><div key={tab.id} className={`open-tab-row ${tab.id===currentPath?'is-active':''}`}>
            <Dropdown.Item className="open-tab-link" onSelect={()=>navigate(tab.path)} title={tab.path}><BookOpen size={14}/><span>{tab.title}</span>{tab.id===currentPath&&<span className="sr-only">Current tab</span>}</Dropdown.Item>
            {!tab.pinned&&<Dropdown.Item className="open-tab-close" aria-label={`Close ${tab.title}`} onSelect={event=>{event.preventDefault();close(tab.id);}}><X size={14}/></Dropdown.Item>}
          </div>)}{!visible.length&&<p className="p-4 text-xs text-slate-500">No matching tabs.</p>}</div>
          <Dropdown.Separator className="my-1 h-px bg-slate-100"/>
          <Dropdown.Item className="tab-command" disabled={!current || current.pinned} onSelect={()=>current&&close(current.id)}>Close current tab</Dropdown.Item>
          <Dropdown.Item className="tab-command" disabled={!current || tabs.filter(t=>!t.pinned&&t.id!==current.id).length===0} onSelect={()=>{if(current){const path=closeOtherTabs(current.id);if(path)navigate(path);}}}>Close other tabs</Dropdown.Item>
          <Dropdown.Item className="tab-command" disabled={!current || !tabs.slice(tabs.findIndex(t=>t.id===current.id)+1).some(t=>!t.pinned)} onSelect={()=>{if(current)closeTabsToRight(current.id);}}>Close tabs after current</Dropdown.Item>
          <Dropdown.Item className="tab-command" disabled={!closable} onSelect={()=>navigate(closeAllTabs())}>Close all tabs</Dropdown.Item>
          <Dropdown.Item className="tab-command" disabled={!closedTabs.length} onSelect={reopen}><RotateCcw size={13}/>Reopen last closed<span className="ml-auto text-[10px] text-slate-400">Ctrl+Shift+T</span></Dropdown.Item>
        </Dropdown.Content></Dropdown.Portal>
      </Dropdown.Root>
      <button type="button" className="module-tab-icon" aria-label="Close current tab" title="Close current tab" disabled={!current||current.pinned} onClick={()=>current&&close(current.id)}><X size={15}/></button>
      <button type="button" className="module-tab-icon" aria-label="Reopen closed tab" title="Reopen closed tab (Ctrl+Shift+T)" disabled={!closedTabs.length} onClick={reopen}><RotateCcw size={15}/></button>
    </div>
  </div>;
}

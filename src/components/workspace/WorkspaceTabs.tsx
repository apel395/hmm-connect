import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, LayoutDashboard, RotateCcw, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import WorkspaceBackButton from "./WorkspaceBackButton";
import useWorkspaceTabs from "@/store/workspaceTabs";
import { workspaceTabGroup, workspaceTitle } from "./workspaceTitle";

const MAX_VISIBLE_TABS = 8;

export default function WorkspaceTabs() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const stripRef = useRef<HTMLDivElement>(null);
  const [visibleLimit, setVisibleLimit] = useState(6);
  useEffect(() => {
    const strip = stripRef.current;
    if (!strip) return;
    const measure = () => setVisibleLimit(Math.max(1, Math.min(MAX_VISIBLE_TABS, Math.floor(strip.clientWidth / 148))));
    measure();
    const observer = new ResizeObserver(measure); observer.observe(strip);
    return () => observer.disconnect();
  }, []);
  const [contextMenu, setContextMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const {
    tabs,
    closedTabs,
    ensureTab,
    closeTab,
    closeOtherTabs,
    closeTabsToRight,
    closeAllTabs,
    reopenLastClosed,
  } = useWorkspaceTabs();
  const activatedPath = useRef("");
  const currentPath = `${location.pathname}${location.search}`;

  useEffect(() => {
    // Workspace navigation can revisit long-lived detail tabs after another
    // screen changed the same record. Refresh active route data on every tab
    // activation instead of relying on component mount semantics.
    if (location.pathname === "/inventory" && activatedPath.current === "/inventory") return;
    activatedPath.current = location.pathname;
    void queryClient.invalidateQueries({ refetchType: "active" });
  }, [currentPath, queryClient, location.pathname]);

  useEffect(() => {
    if (location.pathname === "/" || location.pathname.endsWith("/print")) return;
    const title = workspaceTitle(location.pathname, location.search);
    ensureTab({
      id: currentPath,
      path: currentPath,
      title,
      pinned: location.pathname === "/dashboard",
      group: workspaceTabGroup(location.pathname),
    });
    document.title = `${title} · MMH-Connect`;
  }, [currentPath, ensureTab, location.pathname, location.search]);

  const { visibleTabs, overflowTabs } = useMemo(() => {
    if (tabs.length <= visibleLimit) return { visibleTabs: tabs, overflowTabs: [] };
    const priority = [...tabs].sort((a, b) => {
      if (a.id === currentPath) return -1;
      if (b.id === currentPath) return 1;
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return Number(b.lastActiveAt || 0) - Number(a.lastActiveAt || 0);
    });
    const visibleIds = new Set(priority.slice(0, visibleLimit).map((tab) => tab.id));
    return {
      visibleTabs: tabs.filter((tab) => visibleIds.has(tab.id)),
      overflowTabs: tabs.filter((tab) => !visibleIds.has(tab.id)),
    };
  }, [currentPath, tabs, visibleLimit]);

  useEffect(() => {
    const active = stripRef.current?.querySelector<HTMLElement>("[data-active='true']");
    active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }, [currentPath, visibleTabs.length]);

  useEffect(() => {
    const dismiss = () => setContextMenu(null);
    window.addEventListener("pointerdown", dismiss);
    window.addEventListener("blur", dismiss);
    return () => {
      window.removeEventListener("pointerdown", dismiss);
      window.removeEventListener("blur", dismiss);
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || !event.shiftKey || event.key.toLowerCase() !== "t") return;
      const path = reopenLastClosed();
      if (path) {
        event.preventDefault();
        navigate(path);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, reopenLastClosed]);

  const close = (id: string) => {
    const closingActive = id === currentPath;
    const { nextPath } = closeTab(id);
    if (closingActive && nextPath) navigate(nextPath);
  };

  const tabElement = (tab: (typeof tabs)[number]) => {
    const active = tab.id === currentPath;
    return (
      <div
        key={tab.id}
        data-active={active ? "true" : "false"}
        onContextMenu={(event) => {
          event.preventDefault();
          setContextMenu({
            id: tab.id,
            x: Math.min(event.clientX, window.innerWidth - 210),
            y: Math.min(event.clientY, window.innerHeight - 190),
          });
        }}
        onMouseDown={(event) => {
          if (event.button === 1 && !tab.pinned) {
            event.preventDefault();
            close(tab.id);
          }
        }}
        className={`group relative flex min-w-0 flex-1 max-w-[220px] items-stretch border-r border-slate-200 text-xs transition ${active ? "bg-white text-emerald-900" : "bg-[#F3F5F7] text-slate-500 hover:bg-slate-200/60"}`}
      >
        <button
          type="button"
          title={tab.title}
          onClick={() => navigate(tab.path)}
          className="flex min-w-0 flex-1 items-center gap-2 px-3 text-left"
        >
          {tab.pinned && <LayoutDashboard className="h-3.5 w-3.5 shrink-0 text-[#0F6758]" />}
          <span className="min-w-0 flex-1 truncate font-medium">{tab.title}</span>
        </button>
        {!tab.pinned && (
          <button
            type="button"
            aria-label={`Close ${tab.title}`}
            onClick={() => close(tab.id)}
            className="mr-1 grid w-6 shrink-0 place-items-center self-center rounded opacity-50 hover:bg-black/10 hover:opacity-100"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
        {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#0F6758]" />}
      </div>
    );
  };

  const target = contextMenu ? tabs.find((tab) => tab.id === contextMenu.id) : undefined;
  const targetIndex = target ? tabs.findIndex((tab) => tab.id === target.id) : -1;
  const tabsToRight = targetIndex >= 0 ? tabs.slice(targetIndex + 1) : [];
  const hasClosableRight = tabsToRight.some((tab) => !tab.pinned);
  const activeWillCloseToRight = tabsToRight.some((tab) => tab.id === currentPath && !tab.pinned);

  return (
    <div className="mmh-workspace-tabs flex h-9 shrink-0 items-stretch border-b border-slate-200 bg-[#F3F5F7] print:hidden">
      <div className="flex shrink-0 items-center border-r px-1"><WorkspaceBackButton /></div>
      <div ref={stripRef} className="min-w-0 flex-1 overflow-hidden">
        <div className="flex h-full min-w-0 items-stretch">
          {visibleTabs.map(tabElement)}
        </div>
      </div>

      {overflowTabs.length > 0 && (
        <details className="group/more relative shrink-0 border-l border-slate-200">
          <summary className="flex h-full cursor-pointer list-none items-center gap-1 px-3 text-xs text-[#5F665F] hover:bg-slate-200/60">
            More Tabs ({overflowTabs.length}) <ChevronDown className="h-3.5 w-3.5" />
          </summary>
          <div className="absolute right-0 top-full z-50 mt-1 max-h-80 w-64 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-xl">
            {overflowTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={(event) => {
                  navigate(tab.path);
                  event.currentTarget.closest("details")?.removeAttribute("open");
                }}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs hover:bg-slate-50"
              >
                <span className="truncate">{tab.title}</span>
                <span
                  role="button"
                  aria-label={`Close ${tab.title}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    close(tab.id);
                  }}
                  className="rounded p-1 hover:bg-slate-200"
                >
                  <X className="h-3.5 w-3.5" />
                </span>
              </button>
            ))}
          </div>
        </details>
      )}

      <button
        type="button"
        title="Close all tabs"
        disabled={!tabs.some((tab) => !tab.pinned)}
        onClick={() => navigate(closeAllTabs())}
        className="grid w-8 shrink-0 place-items-center border-l border-slate-200 text-[#6F756F] hover:bg-slate-200/60 disabled:cursor-default disabled:opacity-30"
      >
        <X className="h-4 w-4" />
      </button>
      <button
        type="button"
        title={closedTabs.length ? "Reopen closed tab (Ctrl+Shift+T)" : "No closed tabs"}
        disabled={!closedTabs.length}
        onClick={() => {
          const path = reopenLastClosed();
          if (path) navigate(path);
        }}
        className="grid w-8 shrink-0 place-items-center border-l border-slate-200 text-[#6F756F] hover:bg-slate-200/60 disabled:cursor-default disabled:opacity-30"
      >
        <RotateCcw className="h-4 w-4" />
      </button>

      {contextMenu && target && (
        <div
          role="menu"
          onPointerDown={(event) => event.stopPropagation()}
          style={{ left: contextMenu.x, top: contextMenu.y }}
          className="fixed z-[100] w-52 rounded-md border border-slate-200 bg-white py-1 text-xs shadow-xl"
        >
          <button type="button" disabled={target.pinned} onClick={() => { close(target.id); setContextMenu(null); }} className="block w-full px-3 py-2 text-left hover:bg-slate-50 disabled:opacity-40">Close</button>
          <button type="button" onClick={() => { const path = closeOtherTabs(target.id); if (path) navigate(path); setContextMenu(null); }} className="block w-full px-3 py-2 text-left hover:bg-slate-50">Close Others</button>
          <button type="button" disabled={!hasClosableRight} onClick={() => { const path = closeTabsToRight(target.id); if (activeWillCloseToRight) navigate(path || "/dashboard"); setContextMenu(null); }} className="block w-full px-3 py-2 text-left hover:bg-slate-50 disabled:opacity-40">Close Tabs to the Right</button>
          <button type="button" onClick={() => { navigate(closeAllTabs()); setContextMenu(null); }} className="block w-full px-3 py-2 text-left text-red-600 hover:bg-red-50">Close All</button>
        </div>
      )}
    </div>
  );
}

import { useEffect, useRef } from "react";
import { LayoutDashboard, RotateCcw, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import useWorkspaceTabs from "@/store/workspaceTabs";
import { workspaceTitle } from "./workspaceTitle";

export default function WorkspaceTabs() {
  const location = useLocation();
  const navigate = useNavigate();
  const stripRef = useRef<HTMLDivElement>(null);
  const { tabs, closedTabs, ensureTab, closeTab, reopenLastClosed } = useWorkspaceTabs();
  const currentPath = `${location.pathname}${location.search}`;

  useEffect(() => {
    if (location.pathname.endsWith("/print")) return;
    ensureTab({
      id: currentPath,
      path: currentPath,
      title: workspaceTitle(location.pathname, location.search),
      pinned: location.pathname === "/dashboard",
    });
    document.title = `${workspaceTitle(location.pathname, location.search)} · HMM-Connect`;
  }, [currentPath, ensureTab, location.pathname, location.search]);

  useEffect(() => {
    const active = stripRef.current?.querySelector<HTMLElement>(`[data-tab-id="${CSS.escape(currentPath)}"]`);
    active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }, [currentPath, tabs.length]);

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

  return (
    <div className="flex h-10 shrink-0 items-stretch border-b border-[#DCD6CB] bg-[#F3F0EA]">
      <div ref={stripRef} className="min-w-0 flex-1 overflow-x-auto overflow-y-hidden [scrollbar-width:thin]">
        <div className="flex h-full min-w-max items-stretch">
          {tabs.map((tab) => {
            const active = tab.id === currentPath;
            return (
              <button
                key={tab.id}
                type="button"
                data-tab-id={tab.id}
                title={tab.title}
                onClick={() => navigate(tab.path)}
                onAuxClick={(event) => {
                  if (event.button === 1 && !tab.pinned) close(tab.id);
                }}
                className={`group relative flex min-w-[132px] max-w-[240px] items-center gap-2 border-r border-[#DCD6CB] px-3 text-left text-xs transition ${active ? "bg-white text-[#202723]" : "bg-[#F3F0EA] text-[#666C68] hover:bg-[#EDE9E1]"}`}
              >
                {tab.pinned && <LayoutDashboard className="h-3.5 w-3.5 shrink-0 text-[#0F6758]" />}
                <span className="min-w-0 flex-1 truncate font-medium">{tab.title}</span>
                {!tab.pinned && (
                  <span
                    role="button"
                    aria-label={`Close ${tab.title}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      close(tab.id);
                    }}
                    className="grid h-5 w-5 shrink-0 place-items-center rounded opacity-50 hover:bg-black/10 hover:opacity-100"
                  >
                    <X className="h-3.5 w-3.5" />
                  </span>
                )}
                {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#0F6758]" />}
              </button>
            );
          })}
        </div>
      </div>
      <button
        type="button"
        title={closedTabs.length ? "Reopen closed tab (Ctrl+Shift+T)" : "No closed tabs"}
        disabled={!closedTabs.length}
        onClick={() => {
          const path = reopenLastClosed();
          if (path) navigate(path);
        }}
        className="grid w-10 shrink-0 place-items-center border-l border-[#DCD6CB] text-[#6F756F] hover:bg-[#EDE9E1] disabled:cursor-default disabled:opacity-30"
      >
        <RotateCcw className="h-4 w-4" />
      </button>
    </div>
  );
}

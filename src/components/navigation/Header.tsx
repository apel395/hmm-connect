import {
  Bell,
  Settings,
  LogOut,
  Menu,
  PanelLeftOpen,
  PanelLeftClose,
} from "lucide-react";
import { Link } from "react-router-dom";
import useAuthStore from "@/store/auth";

interface Props {
  onMenuClick: () => void;
  sidebarCollapsed: boolean;
  onSidebarToggle: () => void;
}

export default function Header({
  onMenuClick,
  sidebarCollapsed,
  onSidebarToggle,
}: Props) {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const name = user?.full_name || user?.username || "Hotel User";
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase();

  return (
    <header className="z-30 flex h-12 shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <button
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] lg:hidden"
          aria-label="Open navigation"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
        </button>
        <button
          type="button"
          className="hidden rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] lg:block"
          aria-label={
            sidebarCollapsed ? "Expand navigation" : "Collapse navigation"
          }
          aria-expanded={!sidebarCollapsed}
          title={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
          onClick={onSidebarToggle}
        >
          {sidebarCollapsed ? (
            <PanelLeftOpen className="h-5 w-5" />
          ) : (
            <PanelLeftClose className="h-5 w-5" />
          )}
        </button>
        <div className="truncate text-[13px] font-semibold">
          Hotel Mutiara Merdeka Pekanbaru
        </div>
      </div>

      <div className="flex items-center gap-1 sm:gap-2">
        <Link
          to="/notifications"
          className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]"
          aria-label="Notifications"
        >
          <Bell className="h-[18px] w-[18px]" />
        </Link>
        <Link
          to="/settings"
          className="hidden rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] sm:block"
          aria-label="Settings"
          title="Settings"
        >
          <Settings className="h-[18px] w-[18px]" />
        </Link>
        <div className="ml-1 flex items-center gap-2 border-l border-slate-200 pl-3">
          <div
            className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-50 text-[10px] font-bold text-emerald-800"
            aria-hidden="true"
          >
            {initials || "MM"}
          </div>
          <span className="hidden max-w-32 truncate text-xs font-medium sm:block">
            {name}
          </span>
          <button
            type="button"
            title={`Sign out ${name}`}
            aria-label="Sign out"
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            onClick={logout}
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </header>
  );
}

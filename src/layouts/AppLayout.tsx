import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "@/components/navigation/Sidebar";
import Header from "@/components/navigation/Header";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("navigation-expanded") !== "true");
  useEffect(() => window.localStorage.setItem("navigation-expanded", String(!sidebarCollapsed)), [sidebarCollapsed]);
  const location = useLocation();

  if (location.pathname.endsWith("/print")) {
    return <><div className="p-2 print:hidden"><WorkspaceBackButton /></div><Outlet /></>;
  }

  return (
    <div data-app-print-shell className="flex h-screen overflow-hidden bg-[#F8F6F1] text-[#202723]">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(value => !value)} />
      <div data-app-print-content className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} sidebarCollapsed={sidebarCollapsed} onSidebarToggle={() => setSidebarCollapsed(value => !value)} />
        <div className="print:hidden"><WorkspaceTabs /></div>
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <div data-workspace-content className="w-full p-2 sm:p-3">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

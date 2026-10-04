import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "@/components/navigation/Sidebar";
import Header from "@/components/navigation/Header";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  if (location.pathname.endsWith("/print")) {
    return <Outlet />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F8F6F1] text-[#202723]">
      {sidebarOpen && <Sidebar open onClose={() => setSidebarOpen(false)} />}
      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <WorkspaceTabs />
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <div data-workspace-content className="w-full p-2 sm:p-3">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

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
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <WorkspaceTabs />
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <div className="mx-auto w-full max-w-[1600px] p-3 sm:p-4 lg:p-5">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

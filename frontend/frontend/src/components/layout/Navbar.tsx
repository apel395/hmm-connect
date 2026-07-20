import { Bell, Search } from "lucide-react";

import { useCurrentUser } from "../../features/auth/useAuth";

export function Navbar() {
  const { data: user } = useCurrentUser();
  const initials = user?.full_name
    ?.split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "U";

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div className="flex w-96 items-center gap-3 rounded-lg bg-slate-100 px-3 py-2">
        <Search size={18} className="text-slate-400" />
        <input
          type="text"
          placeholder="Search..."
          className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
        />
      </div>

      <div className="flex items-center gap-4">
        <button className="relative text-slate-500 hover:text-slate-900">
          <Bell size={20} />
          <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-red-500" />
        </button>

        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-700">
            {initials}
          </div>

          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-slate-900">
              {user?.full_name ?? "Loading..."}
            </p>
            <p className="text-xs text-slate-500">
              {user?.roles?.[0]?.name ?? user?.department?.name ?? "ERP User"}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}

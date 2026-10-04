import { Bell, CircleHelp, Menu } from "lucide-react";
import { Link } from "react-router-dom";
import useAuthStore from "@/store/auth";

interface Props {
  onMenuClick: () => void;
}

export default function Header({ onMenuClick }: Props) {
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
    <header className="z-30 flex h-14 shrink-0 items-center justify-between border-b border-[#E8E2D8] bg-white/95 px-4 backdrop-blur sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <button
          className="rounded-lg p-2 text-[#6F756F] hover:bg-[#F8F6F1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]"
          aria-label="Open navigation"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="truncate text-sm font-semibold sm:text-base">
          Hotel Mutiara Merdeka Pekanbaru
        </div>
      </div>

      <div className="flex items-center gap-1 sm:gap-2">
        <Link
          to="/notifications"
          className="relative rounded-lg p-2 text-[#6F756F] hover:bg-[#F8F6F1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]"
          aria-label="Notifications"
        >
          <Bell className="h-[18px] w-[18px]" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[#C49A4A]" />
        </Link>
        <Link
          to="/settings"
          className="hidden rounded-lg p-2 text-[#6F756F] hover:bg-[#F8F6F1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] sm:block"
          aria-label="Help"
        >
          <CircleHelp className="h-[18px] w-[18px]" />
        </Link>
        <div className="ml-1 flex items-center gap-2 border-l border-[#E8E2D8] pl-3">
          <button
            className="grid h-8 w-8 place-items-center rounded-full bg-[#0F6758] text-xs font-bold text-white sm:hidden"
            aria-label="Sign out"
            title={`Sign out ${name}`}
            onClick={logout}
          >
            {initials || "HU"}
          </button>
          <div className="hidden max-w-32 sm:block">
            <div className="truncate text-sm font-semibold">{name}</div>
            <button
              className="text-xs text-[#6F756F] hover:text-[#086B5A] hover:underline"
              onClick={logout}
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

import { Link, NavLink, Outlet } from "react-router";
import { LayoutGrid, MessageSquareText, UserRound, LogOut } from "lucide-react";

import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

function SidebarItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
          isActive ? "bg-neutral-100 text-neutral-900" : "text-neutral-600 hover:bg-neutral-50",
        )
      }
    >
      {icon}
      <span>{label}</span>
    </NavLink>
  );
}

export default function MainLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="grid h-screen grid-cols-[240px_1fr] bg-white text-neutral-900">
      <aside className="flex flex-col border-r border-neutral-200 bg-neutral-50/60 p-4">
        <Link to="/" className="mb-6 flex items-center gap-2 px-2 text-lg font-semibold tracking-tight">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-neutral-900 text-white text-[11px] font-bold">J</span>
          Jockey
        </Link>

        <nav className="flex flex-col gap-1">
          <SidebarItem to="/workspace" icon={<LayoutGrid size={16} />} label="Workspace" />
          <SidebarItem to="/chat" icon={<MessageSquareText size={16} />} label="Chat" />
          <SidebarItem to="/profile" icon={<UserRound size={16} />} label="Profile" />
        </nav>

        <div className="mt-auto flex items-center gap-3 rounded-md border border-neutral-200 bg-white p-2 text-xs">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-neutral-100 text-neutral-700">
            {user?.email?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div className="flex flex-col leading-tight">
            <span className="truncate text-neutral-900">{user?.email}</span>
            <span className="text-[10px] uppercase text-neutral-500">{user?.role}</span>
          </div>
          <button onClick={logout} className="ml-auto rounded p-1 text-neutral-500 hover:bg-neutral-100" title="Sign out">
            <LogOut size={14} />
          </button>
        </div>
      </aside>

      <main className="overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

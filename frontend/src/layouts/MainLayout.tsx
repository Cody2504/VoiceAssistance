import { Link, NavLink, Outlet } from "react-router";
import { useTranslation } from "react-i18next";
import { Plus, PanelLeftOpen, ShieldCheck, Users as UsersIcon, CreditCard, ClipboardCheck } from "lucide-react";

import { Logo } from "@/components/brand/Logo";
import { TopBar } from "@/components/layout/TopBar";
import {
  OverviewDefault, OverviewFilled,
  IndexesDefault, IndexesFilled,
  AssetsDefault, AssetsFilled,
  EntitiesDefault, EntitiesFilled,
  SearchDefault, SearchFilled,
  AnalyzeDefault, AnalyzeFilled,
  SegmentDefault, SegmentFilled,
  ExamplesDefault, ExamplesFilled,
  SettingsDefault,
  CollapseDefault,
} from "@/components/brand/SidebarIcons";
import { SidebarChats } from "@/components/layout/SidebarChats";
import { SidebarItem } from "@/components/layout/SidebarItem";
import { useAuth } from "@/contexts/AuthContext";
import { SidebarProvider, useSidebar } from "@/contexts/SidebarContext";
import { cn } from "@/lib/utils";

function WorkspaceButton() {
  const { collapsed } = useSidebar();
  const { t } = useTranslation();
  return (
    <NavLink
      to="/workspace"
      title={collapsed ? t("chat.sidebar.new_chat") : undefined}
      data-testid="workspace-menu-button"
      className={({ isActive }) =>
        cn(
          // Border-radius animation (12 → 16) mirrors TwelveLabs' New button.
          "relative flex items-center transition-all duration-200 ease-in-out bg-[var(--color-obsidian)] text-[var(--color-eggshell)] text-[14px] font-medium",
          "rounded-[12px] hover:rounded-[16px] hover:bg-neutral-800",
          collapsed
            ? "h-10 w-10 justify-center p-0"
            : "min-h-10 flex-1 w-full justify-between gap-x-2 px-3 py-2",
          isActive && "ring-1 ring-white/15",
        )
      }
    >
      {collapsed ? (
        <Plus size={16} strokeWidth={2.25} />
      ) : (
        <>
          {/* pr clears the absolutely-positioned + icon so long labels (vi) truncate instead of running under it */}
          <span className="truncate pr-7">{t("chat.sidebar.new_chat")}</span>
          <span className="absolute right-2 flex items-center justify-center">
            <Plus size={16} strokeWidth={2.25} />
          </span>
        </>
      )}
    </NavLink>
  );
}

function SidebarFooter() {
  const { collapsed, toggle } = useSidebar();
  const { t } = useTranslation();

  return (
    <div className="flex flex-col">
      <div className="mt-auto flex flex-col gap-y-1">
        {/* API keys / API docs / Help live as tabs inside Settings — one entry here is enough. */}
        <SidebarItem to="/settings/billing" icon={<SettingsDefault />} label={t("layout.sidebar.settings")} />
      </div>

      <div className="mt-6 flex flex-col gap-y-1">
        <button
          onClick={toggle}
          title={collapsed ? t("layout.sidebar.expand_tooltip") : t("layout.sidebar.collapse_tooltip")}
          data-testid="sidebar-collapse"
          className="flex items-center gap-x-1 relative w-full h-10 px-1 cursor-pointer select-none truncate group"
        >
          {!collapsed && (
            <span
              className="px-2 py-2 text-[15px] leading-tight text-left rounded-lg flex items-center gap-x-2 group-hover:bg-[var(--color-powder)]"
              style={{ width: 128 }}
            >
              {t("layout.sidebar.collapse")}
            </span>
          )}
          <span
            className="absolute w-10 h-10 flex items-center justify-center rounded-lg text-[var(--color-obsidian)]"
            style={{ right: collapsed ? 4 : -4 }}
          >
            {collapsed ? <PanelLeftOpen size={22} strokeWidth={1.75} /> : <CollapseDefault size={24} />}
          </span>
        </button>
      </div>
    </div>
  );
}

function SidebarShell() {
  const { collapsed } = useSidebar();
  const { t } = useTranslation();
  const { user } = useAuth();
  return (
    <nav
      className={cn(
        "h-dvh min-h-[600px] py-5 flex flex-col sticky top-0 bg-[var(--color-eggshell)]",
        "transform transition-[width,padding] duration-300 ease-in-out",
        collapsed ? "px-3 w-[72px]" : "px-5",
      )}
      style={collapsed ? undefined : { width: 204 }}
      id="page-layout-side"
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Link to="/overview" className={cn("inline-block transition-all duration-300", collapsed && "flex justify-center")} aria-label="Jockey">
          {collapsed ? (
            <span
              className="block h-7 w-7 rounded-full"
              style={{ background: "radial-gradient(circle at 30% 30%, #ffd5e2, #c4a8ff 55%, #87e3a5)" }}
            />
          ) : (
            <Logo size="md" />
          )}
        </Link>

        <div className="mt-6 mb-6">
          <WorkspaceButton />
        </div>

        <SidebarChats />

        <div className="flex flex-col gap-y-1">
          <SidebarItem to="/overview" icon={<OverviewDefault />} iconActive={<OverviewFilled />} label={t("layout.sidebar.overview")} />
          <SidebarItem to="/indexes" icon={<IndexesDefault />} iconActive={<IndexesFilled />} label={t("layout.sidebar.indexes")} />
          <SidebarItem to="/assets" icon={<AssetsDefault />} iconActive={<AssetsFilled />} label={t("layout.sidebar.assets")} />
          <SidebarItem to="/entities" icon={<EntitiesDefault />} iconActive={<EntitiesFilled />} label={t("layout.sidebar.entities")} />
        </div>

        <div className="mt-6 flex flex-col gap-y-1">
          <SidebarItem to="/playground/search" icon={<SearchDefault />} iconActive={<SearchFilled />} label={t("layout.sidebar.search")} />
          <SidebarItem to="/playground/analyze" icon={<AnalyzeDefault />} iconActive={<AnalyzeFilled />} label={t("layout.sidebar.analyze")} />
          <SidebarItem to="/playground/segment" icon={<SegmentDefault />} iconActive={<SegmentFilled />} label={t("layout.sidebar.segment")} />
          <SidebarItem to="/examples" icon={<ExamplesDefault />} iconActive={<ExamplesFilled />} label={t("layout.sidebar.examples")} />
        </div>

        {user?.role === "admin" && (
          <div className="mt-6 flex flex-col gap-y-1">
            <SidebarItem to="/admin" end icon={<ShieldCheck size={22} strokeWidth={1.75} />} label={t("admin.nav.overview")} />
            <SidebarItem to="/admin/users" icon={<UsersIcon size={22} strokeWidth={1.75} />} label={t("admin.nav.users")} />
            <SidebarItem to="/admin/billing" icon={<CreditCard size={22} strokeWidth={1.75} />} label={t("admin.nav.billing")} />
            <SidebarItem to="/admin/evaluation" icon={<ClipboardCheck size={22} strokeWidth={1.75} />} label={t("admin.nav.evaluation")} />
          </div>
        )}
      </div>

      <SidebarFooter />
    </nav>
  );
}

export default function MainLayout() {
  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
        <SidebarShell />
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <TopBar />
          <main className="min-w-0 flex-1 overflow-y-auto app-ground">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}

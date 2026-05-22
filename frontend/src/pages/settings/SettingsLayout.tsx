import { NavLink, Outlet } from "react-router";
import { Building2, KeyRound, CreditCard, BarChart3, Gauge, Webhook, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItemDef {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const ITEMS: NavItemDef[] = [
  { to: "/settings/organization", label: "Organization", icon: <Building2 size={17} strokeWidth={1.75} /> },
  { to: "/settings/api-keys",     label: "API keys",     icon: <KeyRound size={17} strokeWidth={1.75} /> },
  { to: "/settings/billing",      label: "Billing & plan", icon: <CreditCard size={17} strokeWidth={1.75} /> },
  { to: "/settings/usage",        label: "Usage",        icon: <BarChart3 size={17} strokeWidth={1.75} /> },
  { to: "/settings/rate-limits",  label: "Rate limits",  icon: <Gauge size={17} strokeWidth={1.75} /> },
  { to: "/settings/webhooks",     label: "Webhooks",     icon: <Webhook size={17} strokeWidth={1.75} /> },
  { to: "/settings/profile",      label: "Profile",      icon: <UserRound size={17} strokeWidth={1.75} /> },
];

/**
 * Settings shell with a left sub-navigation sidebar (mirrors the
 * `/dashboard/*` layout from the TwelveLabs playground reference markup).
 * Sub-pages render inside <Outlet />.
 */
export default function SettingsLayout() {
  return (
    <div className="flex w-full bg-[var(--color-eggshell)]">
      <aside
        className="sticky top-0 hidden flex-col px-[22px] py-5 md:flex"
        style={{ width: 212, minHeight: 600, height: "calc(100vh - 64px)" }}
      >
        <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-slate)]">
          Settings
        </p>
        <nav className="mt-2 flex flex-col gap-y-1">
          {ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className="group flex h-10 items-center gap-x-1 text-[var(--color-obsidian)]"
            >
              {({ isActive }) => (
                <>
                  <span
                    className={cn(
                      "flex-1 rounded-lg p-2 text-[15px] leading-tight transition-colors",
                      isActive ? "bg-[var(--color-chalk)] font-medium" : "group-hover:bg-[var(--color-powder)]",
                    )}
                  >
                    {item.label}
                  </span>
                  <span className="grid h-6 w-6 shrink-0 place-items-center text-[var(--color-obsidian)]">
                    {item.icon}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1 px-5 pr-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-6 px-5 pt-6 pb-20">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

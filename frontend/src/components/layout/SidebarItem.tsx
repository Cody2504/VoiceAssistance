import { NavLink } from "react-router";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/contexts/SidebarContext";

interface SidebarItemProps {
  to: string;
  /** Outline / default-state icon (24×24). */
  icon: ReactNode;
  /** Filled / active-state icon (24×24). Defaults to `icon`. */
  iconActive?: ReactNode;
  label: string;
  end?: boolean;
  /** Mark this link external so it opens in a new tab. */
  external?: boolean;
}

/**
 * Sidebar nav item reproducing the TwelveLabs playground layout:
 * - label span sits left with fixed-ish width and gets a soft gray background
 *   on hover (bg-grey-200) / a darker gray when active (bg-grey-400);
 * - icon is absolutely positioned on the right at -4px, in a 40×40 hover region.
 *
 * The active variant swaps to the filled icon glyph; the outline icon is used
 * by default. Both are rendered and CSS-toggled so SVGs don't remount on hover.
 */
export function SidebarItem({ to, icon, iconActive, label, end, external }: SidebarItemProps) {
  const { collapsed } = useSidebar();
  const filled = iconActive ?? icon;

  if (external) {
    return (
      <a
        href={to}
        target="_blank"
        rel="noreferrer"
        title={collapsed ? label : undefined}
        className="flex items-center gap-x-1 relative w-full h-10 px-1 cursor-pointer select-none truncate group"
      >
        <Inner collapsed={collapsed} label={label} icon={icon} filled={filled} isActive={false} />
      </a>
    );
  }

  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      className="flex items-center gap-x-1 relative w-full h-10 px-1 cursor-pointer select-none truncate group"
    >
      {({ isActive }) => (
        <Inner collapsed={collapsed} label={label} icon={icon} filled={filled} isActive={isActive} />
      )}
    </NavLink>
  );
}

function Inner({
  collapsed,
  label,
  icon,
  filled,
  isActive,
}: {
  collapsed: boolean;
  label: string;
  icon: ReactNode;
  filled: ReactNode;
  isActive: boolean;
}) {
  return (
    <>
      {!collapsed && (
        <span
          className={cn(
            "px-2 py-2 text-[15px] leading-tight text-left rounded-lg flex items-center gap-x-2 transition-colors",
            isActive ? "bg-[var(--color-chalk)] font-medium" : "group-hover:bg-[var(--color-powder)]",
          )}
          style={{ width: 128 }}
        >
          <span className="truncate">{label}</span>
        </span>
      )}
      <span
        className={cn(
          "absolute w-10 h-10 flex items-center justify-center rounded-lg text-[var(--color-obsidian)] transition-colors",
          isActive ? "bg-transparent" : "group-hover:bg-transparent",
        )}
        style={{ right: collapsed ? 4 : -4 }}
      >
        <span className={isActive ? "hidden" : "block group-hover:hidden"}>{icon}</span>
        <span className={isActive ? "block" : "hidden group-hover:block"}>{filled}</span>
      </span>
    </>
  );
}

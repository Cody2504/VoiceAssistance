import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Link } from "react-router";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import { UserMenu } from "./UserMenu";

/**
 * Top app bar shown above main content on every authenticated page.
 * Mirrors the TwelveLabs playground topbar: Used X min / Y hr, Book a Demo,
 * Invite, and a peach avatar pill that opens the user menu.
 */
export function TopBar() {
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const initials = (() => {
    const email = user?.email ?? "";
    const name = email.split("@")[0];
    const parts = name.split(/[._-]/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    if (parts[0]?.length) return parts[0].slice(0, 2).toUpperCase();
    return "?";
  })();

  return (
    <div className="sticky top-0 z-30 flex h-14 items-center justify-end gap-2 border-b border-[var(--color-chalk)] bg-[var(--color-eggshell)]/85 px-6 backdrop-blur">
      <Link
        to="/pricing"
        className="hidden text-[13px] text-[var(--color-gravel)] hover:text-[var(--color-obsidian)] md:inline mr-2"
      >
        Used <span className="text-[var(--color-obsidian)]">0 min</span> / 10 hr
      </Link>

      <TopBarButton>Book a Demo</TopBarButton>
      <TopBarButton rightIcon={<UserPlus size={14} />}>Invite</TopBarButton>

      <div className="relative">
        <button
          type="button"
          aria-label="user-account-menu"
          onClick={() => setMenuOpen((o) => !o)}
          className="grid h-8 min-w-[52px] place-items-center rounded-lg bg-[#fdd6b3] px-2 py-[3px] text-[13px] font-medium text-[var(--color-obsidian)] transition hover:brightness-95"
        >
          {initials}
        </button>
        {menuOpen && <UserMenu initials={initials} onClose={() => setMenuOpen(false)} />}
      </div>
    </div>
  );
}

function TopBarButton({
  children,
  rightIcon,
}: {
  children: React.ReactNode;
  rightIcon?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={cn(
        "relative inline-flex h-8 items-center gap-x-1 px-3 text-[13px] text-[var(--color-obsidian)] transition-all duration-200",
        "rounded-[10px] shadow-[0_0_0_1px_var(--color-chalk)_inset] hover:bg-black/5 hover:rounded-[12px]",
      )}
    >
      <span>{children}</span>
      {rightIcon}
    </button>
  );
}

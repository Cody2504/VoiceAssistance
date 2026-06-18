import { useState } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/contexts/AuthContext";
import { useIndexUsage, usageLabel } from "@/hooks/useIndexUsage";
import { UserMenu } from "./UserMenu";
import { IndexingMonitor } from "./IndexingMonitor";

/**
 * Top app bar shown above main content on every authenticated page.
 * Shows Used X / Y, the indexing monitor, and a peach avatar pill that opens
 * the user menu.
 */
export function TopBar() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const { usedMinutes, capMinutes } = useIndexUsage();
  const unlimited = t("settings.billing.unlimited");

  const initials = (() => {
    const email = user?.email ?? "";
    const name = email.split("@")[0];
    const parts = name.split(/[._-]/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    if (parts[0]?.length) return parts[0].slice(0, 2).toUpperCase();
    return "?";
  })();

  return (
    <div className="sticky top-0 z-30 flex h-14 items-center justify-end gap-2 bg-[var(--color-eggshell)]/85 px-6 backdrop-blur">
      <Link
        to="/pricing"
        className="hidden text-[13px] text-[var(--color-gravel)] hover:text-[var(--color-obsidian)] md:inline mr-2"
      >
        {t("layout.usermenu.used")}{" "}
        <span className="text-[var(--color-obsidian)]">{usageLabel(usedMinutes, unlimited)}</span> /{" "}
        {usageLabel(capMinutes, unlimited)}
      </Link>

      <IndexingMonitor />

      <div className="relative">
        <button
          type="button"
          aria-label="user-account-menu"
          onClick={() => setMenuOpen((o) => !o)}
          className="grid h-8 min-w-[52px] place-items-center rounded-lg bg-[#fdd6b3] px-2 py-[3px] text-[13px] font-medium text-[var(--color-obsidian)] transition hover:brightness-95"
        >
          {initials}
        </button>
        {menuOpen && (
          <UserMenu
            initials={initials}
            usedMin={usedMinutes}
            capMin={capMinutes}
            onClose={() => setMenuOpen(false)}
          />
        )}
      </div>
    </div>
  );
}

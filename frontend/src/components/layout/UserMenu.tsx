import { useEffect, useRef } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { Info, ArrowUpRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface Props {
  initials: string;
  onClose: () => void;
}

/**
 * Dropdown card opened from the top-right avatar pill. Mirrors the TwelveLabs
 * playground user menu: avatar, name/email, plan with usage bar, two stat
 * rows, Upgrade pill, Pricing link, Sign out.
 */
export function UserMenu({ initials, onClose }: Props) {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const usedMin = 0;
  const cap = 300; // 5 hr in minutes (free monthly indexing allowance)
  const pct = Math.min(100, (usedMin / cap) * 100);
  const indexingPct = pct * 0.6;
  const analyzePct = pct * 0.4;

  return (
    <div
      ref={ref}
      className="pop-in absolute right-0 top-12 z-50 w-[360px] origin-top-right rounded-2xl border border-[var(--color-chalk)] bg-white p-5 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.18)]"
    >
      <div className="mb-4 flex justify-center">
        <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#fdd6b3] text-[15px] font-medium text-[var(--color-obsidian)]">
          {initials}
        </div>
      </div>
      <div className="mb-5 text-center">
        <p className="text-[15px] font-medium text-[var(--color-obsidian)]">
          {user?.email?.split("@")[0] ?? t("layout.usermenu.user_fallback")}
        </p>
        <p className="mt-0.5 text-[13px] text-[var(--color-gravel)]">{user?.email}</p>
      </div>

      <div className="mb-5 rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)] p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-1 text-[13px] font-medium text-[var(--color-obsidian)]">
            {t("layout.usermenu.free_plan")}
            <Info size={12} className="text-[var(--color-slate)]" />
          </div>
          <div className="text-[13px] text-[var(--color-gravel)]">
            {t("layout.usermenu.used")} <span className="text-[var(--color-obsidian)]">{usedMin} min</span> / 5 hr
          </div>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-chalk)]">
          <div className="absolute inset-y-0 left-0 bg-[#5fb364]" style={{ width: `${indexingPct}%` }} />
          <div
            className="absolute inset-y-0 bg-[#e5b659]"
            style={{ left: `${indexingPct}%`, width: `${analyzePct}%` }}
          />
        </div>
        <div className="mt-2 flex gap-4 text-[11px] text-[var(--color-gravel)]">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-[#5fb364]" /> {t("layout.usermenu.indexing")}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-[#e5b659]" /> {t("layout.usermenu.analyze_segment")}
          </span>
        </div>

        <div className="mt-4 space-y-2 text-[13px]">
          <div className="flex items-center justify-between">
            <span className="text-[var(--color-obsidian)]">{t("layout.usermenu.max_duration")}</span>
            <span className="text-[var(--color-gravel)]">
              <span className="text-[var(--color-obsidian)]">0</span> hr / 10 hr
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[var(--color-obsidian)]">{t("layout.usermenu.max_videos")}</span>
            <span className="text-[var(--color-gravel)]">
              <span className="text-[var(--color-obsidian)]">0</span> videos / 100 videos
            </span>
          </div>
        </div>
      </div>

      <Link
        to="/pricing"
        onClick={onClose}
        className="mb-3 flex h-11 w-full items-center justify-center gap-1.5 rounded-full bg-[var(--color-obsidian)] text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.98]"
      >
        {t("layout.usermenu.upgrade")} ↑
      </Link>

      <div className="space-y-2 text-[13px]">
        <Link
          to="/pricing"
          onClick={onClose}
          className="flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-[var(--color-powder)]"
        >
          <span className="text-[var(--color-obsidian)]">{t("layout.usermenu.pricing")}</span>
          <ArrowUpRight size={13} className="text-[var(--color-gravel)]" />
        </Link>
        <button
          type="button"
          onClick={() => {
            onClose();
            logout();
          }}
          className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
        >
          {t("layout.usermenu.sign_out")}
        </button>
      </div>
    </div>
  );
}

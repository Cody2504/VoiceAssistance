import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import {
  ChevronDown,
  Globe,
  Search,
  Sparkles,
  Layers,
  Boxes,
  type LucideIcon,
} from "lucide-react";
import { Logo } from "@/components/brand/Logo";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

/**
 * Marketing top bar (guest surface), mirroring the TwelveLabs nav:
 *   logo · Platform ▾ · Pricing ▾ · Solutions ▾ · About Us
 *   · 🌐 · Playground (filled pill) · Talk to sales (outlined pill)
 *
 * Menus open on hover/focus and animate in (fade + slide + subtle scale) so
 * they glide rather than snap. prefers-reduced-motion neutralises the motion
 * via the global transition guard in index.css.
 *
 *   - Platform  → "mega": two icon columns, items deep-link to product sections
 *   - Pricing   → "list": plain text list (Compare Plans / Pricing Calculator)
 *   - Solutions → "split": framer-style overlay, enterprise | industries split
 *   - About Us  → plain link, no panel
 *
 * All copy is keyed into the `nav.*` i18n namespace and resolved at render.
 */

interface MenuItem {
  labelKey: string;
  descKey?: string;
  to: string;
  icon?: LucideIcon;
}
interface MenuGroup {
  headingKey?: string;
  items: MenuItem[];
}
interface NavEntry {
  labelKey: string;
  to?: string;
  groups?: MenuGroup[];
  /** mega = wide icon grid · list = narrow text list · split = two-pane overlay */
  variant?: "mega" | "list" | "split";
}

const NAV: NavEntry[] = [
  {
    labelKey: "nav.platform",
    variant: "mega",
    groups: [
      {
        headingKey: "nav.menu.platform_heading",
        items: [
          { labelKey: "nav.menu.platform_overview", descKey: "nav.menu.platform_overview_desc", to: "/product/product-overview", icon: Boxes },
          { labelKey: "nav.menu.models", descKey: "nav.menu.models_desc", to: "/product/product-overview#models", icon: Sparkles },
        ],
      },
      {
        headingKey: "nav.menu.capabilities_heading",
        items: [
          { labelKey: "nav.menu.search", descKey: "nav.menu.search_desc", to: "/product/product-overview#search", icon: Search },
          { labelKey: "nav.menu.analyze", descKey: "nav.menu.analyze_desc", to: "/product/product-overview#analyze", icon: Sparkles },
          { labelKey: "nav.menu.segment", descKey: "nav.menu.segment_desc", to: "/product/product-overview#segment", icon: Layers },
        ],
      },
    ],
  },
  {
    labelKey: "nav.pricing",
    variant: "list",
    groups: [
      {
        items: [
          { labelKey: "nav.menu.compare_plans", to: "/pricing#compare" },
          { labelKey: "nav.menu.pricing_calculator", to: "/pricing-calculator" },
        ],
      },
    ],
  },
  {
    labelKey: "nav.solutions",
    variant: "split",
    groups: [
      // left pane — enterprise
      {
        items: [{ labelKey: "nav.menu.enterprise_overview", to: "/solutions" }],
      },
      // right pane — by industry
      {
        headingKey: "nav.menu.solutions_heading",
        items: [
          { labelKey: "nav.menu.media_entertainment", to: "/solutions/media-and-entertainment" },
          { labelKey: "nav.menu.advertising", to: "/solutions/advertising" },
          { labelKey: "nav.menu.government_security", to: "/solutions/government-and-security" },
          { labelKey: "nav.menu.automotive", to: "/solutions/automotive" },
        ],
      },
    ],
  },
  { labelKey: "nav.about", to: "/" },
];

const LANGS = [
  { code: "en", label: "English" },
  { code: "vi", label: "Tiếng Việt" },
];

export function NavBar() {
  const { user } = useAuth();
  const { i18n, t } = useTranslation();
  const [open, setOpen] = useState<string | null>(null);
  const [langOpen, setLangOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The marketing surface is one light eggshell theme everywhere (ElevenLabs style).
  const isDarkHome = false;

  // hover with a small close delay so the cursor can travel into the panel
  function openMenu(label: string) {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(label);
  }
  function scheduleClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(null), 120);
  }
  useEffect(() => () => { if (closeTimer.current) clearTimeout(closeTimer.current); }, []);

  // Esc closes any open menu
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") { setOpen(null); setLangOpen(false); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const currentLang = LANGS.find((l) => i18n.language?.startsWith(l.code)) ?? LANGS[0];

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b backdrop-blur",
        isDarkHome
          ? "border-white/10 bg-[#050606]/86 text-[#f4f2ea]"
          : "border-[var(--color-chalk)] bg-[var(--color-eggshell)]/85"
      )}
    >
      {/* soft gradient wash bleeding from the right (topbar.png) */}
      {!isDarkHome && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-0 w-1/2"
          style={{
            background:
              "linear-gradient(90deg, rgba(253,252,252,0) 0%, rgba(168,230,178,0.16) 55%, rgba(255,196,156,0.18) 78%, rgba(246,175,255,0.20) 100%)",
          }}
        />
      )}

      <div className="relative mx-auto flex h-16 max-w-[1280px] items-center gap-7 px-6">
        <Link
          to="/"
          className={cn("flex h-16 shrink-0 items-center", isDarkHome && "text-[#f4f2ea]")}
          aria-label="Jockey"
        >
          <Logo size="sm" />
        </Link>

        {/* center nav */}
        <nav className="hidden items-center gap-1 lg:flex" onMouseLeave={scheduleClose}>
          {NAV.map((entry) =>
            entry.groups ? (
              <div
                key={entry.labelKey}
                className="relative"
                onMouseEnter={() => openMenu(entry.labelKey)}
              >
                <button
                  type="button"
                  aria-expanded={open === entry.labelKey}
                  aria-haspopup="true"
                  onFocus={() => openMenu(entry.labelKey)}
                  onClick={() => setOpen(open === entry.labelKey ? null : entry.labelKey)}
                  className={cn(
                    "inline-flex cursor-pointer items-center gap-1 rounded-lg px-3 py-2 text-[14px] transition",
                    isDarkHome
                      ? open === entry.labelKey
                        ? "text-white"
                        : "text-white/72 hover:text-white"
                      : open === entry.labelKey
                        ? "text-[var(--color-obsidian)]"
                        : "text-[var(--color-obsidian)]/80 hover:text-[var(--color-obsidian)]"
                  )}
                >
                  {t(entry.labelKey)}
                  <ChevronDown
                    size={14}
                    className={cn("transition-transform duration-200", open === entry.labelKey && "rotate-180")}
                  />
                </button>

                {/* always mounted so it can animate both in and out */}
                <div
                  aria-hidden={open !== entry.labelKey}
                  className={cn(
                    "absolute left-0 top-full z-50 origin-top pt-2 transition duration-200 ease-out",
                    open === entry.labelKey
                      ? "translate-y-0 scale-100 opacity-100"
                      : "pointer-events-none -translate-y-1 scale-[0.98] opacity-0"
                  )}
                >
                  <MenuPanel entry={entry} onNavigate={() => setOpen(null)} />
                </div>
              </div>
            ) : (
              <Link
                key={entry.labelKey}
                to={entry.to!}
                className={cn(
                  "rounded-lg px-3 py-2 text-[14px] transition",
                  isDarkHome
                    ? "text-white/72 hover:text-white"
                    : "text-[var(--color-obsidian)]/80 hover:text-[var(--color-obsidian)]"
                )}
              >
                {t(entry.labelKey)}
              </Link>
            )
          )}
        </nav>

        {/* right cluster */}
        <div className="ml-auto flex items-center gap-2">
          {/* language switcher */}
          <div
            className="relative hidden sm:block"
            onMouseEnter={() => setLangOpen(true)}
            onMouseLeave={() => setLangOpen(false)}
          >
            <button
              type="button"
              aria-label={t("nav.select_language")}
              aria-expanded={langOpen}
              onClick={() => setLangOpen((v) => !v)}
              className={cn(
                "inline-flex h-9 cursor-pointer items-center gap-1 rounded-full px-2.5 text-[13px] transition",
                isDarkHome
                  ? "text-white/70 hover:text-white"
                  : "text-[var(--color-obsidian)]/80 hover:text-[var(--color-obsidian)]"
              )}
            >
              <Globe size={16} />
              <ChevronDown size={13} />
            </button>
            <div
              aria-hidden={!langOpen}
              className={cn(
                "absolute right-0 top-full z-50 mt-1 w-40 origin-top-right rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-[0_20px_50px_-25px_rgba(0,0,0,0.4)] transition duration-200 ease-out",
                langOpen
                  ? "translate-y-0 scale-100 opacity-100"
                  : "pointer-events-none -translate-y-1 scale-[0.98] opacity-0"
              )}
            >
              {LANGS.map((l) => (
                <button
                  key={l.code}
                  onClick={() => { void i18n.changeLanguage(l.code); setLangOpen(false); }}
                  className={cn(
                    "flex w-full cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-left text-[13px] transition hover:bg-[var(--color-powder)]",
                    currentLang.code === l.code ? "text-[var(--color-obsidian)]" : "text-[var(--color-gravel)]"
                  )}
                >
                  {l.label}
                  {currentLang.code === l.code && <span className="text-[var(--color-accent-blue)]">●</span>}
                </button>
              ))}
            </div>
          </div>

          {user ? (
            <Link
              to="/overview"
              className={cn(
                "inline-flex h-9 cursor-pointer items-center rounded-full px-4 text-[13px] font-medium transition",
                isDarkHome
                  ? "bg-[#f4f2ea] text-[#050606] hover:bg-white"
                  : "bg-[var(--color-obsidian)] text-white hover:bg-neutral-800"
              )}
            >
              {t("nav.open_app")} ↗
            </Link>
          ) : (
            <>
              <Link
                to="/signup"
                className={cn(
                  "inline-flex h-9 cursor-pointer items-center gap-1 rounded-full px-4 text-[13px] font-medium transition",
                  isDarkHome
                    ? "bg-[#f4f2ea] text-[#050606] hover:bg-white"
                    : "bg-[var(--color-obsidian)] text-white hover:bg-neutral-800"
                )}
              >
                {t("nav.playground_cta")} ↗
              </Link>
              <a
                href="/#cta"
                className={cn(
                  "hidden h-9 cursor-pointer items-center rounded-full border px-4 text-[13px] font-medium transition sm:inline-flex",
                  isDarkHome
                    ? "border-white/14 text-[#f4f2ea] hover:border-white/35 hover:bg-white/[0.04]"
                    : "border-[var(--color-chalk)] bg-white text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
                )}
              >
                {t("nav.talk_to_sales")} ↗
              </a>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

const CARD =
  "rounded-2xl border border-[var(--color-chalk)] bg-white p-3 shadow-[0_30px_80px_-35px_rgba(0,0,0,0.45)]";
const EYEBROW =
  "px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]";

function MenuPanel({ entry, onNavigate }: { entry: NavEntry; onNavigate: () => void }) {
  const { t } = useTranslation();
  if (entry.variant === "split") return <SplitPanel entry={entry} onNavigate={onNavigate} />;

  const isMega = entry.variant === "mega";
  return (
    <div className={cn(CARD, isMega ? "w-[560px]" : "w-56")}>
      <div className={cn("grid gap-x-3", isMega ? "grid-cols-2 gap-y-1" : "grid-cols-1")}>
        {entry.groups!.map((group, gi) => (
          <div key={gi}>
            {group.headingKey && <p className={EYEBROW}>{t(group.headingKey)}</p>}
            {group.items.map((item) =>
              isMega ? (
                <RichItem key={item.labelKey + item.to} item={item} onNavigate={onNavigate} />
              ) : (
                <TextItem key={item.labelKey + item.to} item={item} onNavigate={onNavigate} />
              )
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Framer-style "SOLUTIONS-OVERLAY": enterprise pane | divider | industries pane. */
function SplitPanel({ entry, onNavigate }: { entry: NavEntry; onNavigate: () => void }) {
  const { t } = useTranslation();
  const [left, right] = entry.groups!;
  return (
    <div className={cn(CARD, "w-[600px]")}>
      <div className="flex items-stretch">
        <div className="w-[214px] shrink-0 pr-2">
          {left.headingKey && <p className={EYEBROW}>{t(left.headingKey)}</p>}
          {left.items.map((item) => (
            <TextItem key={item.labelKey + item.to} item={item} onNavigate={onNavigate} />
          ))}
        </div>
        <div aria-hidden className="mx-1 w-px self-stretch bg-[var(--color-chalk)]" />
        <div className="flex-1 pl-2">
          {right.headingKey && <p className={EYEBROW}>{t(right.headingKey)}</p>}
          {right.items.map((item) => (
            <TextItem key={item.labelKey + item.to} item={item} onNavigate={onNavigate} />
          ))}
        </div>
      </div>
    </div>
  );
}

/** Icon + title + description row (Platform mega menu). */
function RichItem({ item, onNavigate }: { item: MenuItem; onNavigate: () => void }) {
  const { t } = useTranslation();
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      className="group flex items-start gap-3 rounded-xl px-3 py-2 transition hover:bg-[var(--color-powder)]"
    >
      {Icon && (
        <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--color-chalk)] bg-[var(--color-eggshell)] text-[var(--color-obsidian)] transition group-hover:border-[var(--color-accent-blue)] group-hover:text-[var(--color-accent-blue)]">
          <Icon size={16} />
        </span>
      )}
      <span>
        <span className="block text-[14px] font-medium text-[var(--color-obsidian)]">{t(item.labelKey)}</span>
        {item.descKey && (
          <span className="block text-[12px] leading-snug text-[var(--color-gravel)]">{t(item.descKey)}</span>
        )}
      </span>
    </Link>
  );
}

/** Plain text row (Pricing list + Solutions split). */
function TextItem({ item, onNavigate }: { item: MenuItem; onNavigate: () => void }) {
  const { t } = useTranslation();
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      className="block rounded-xl px-3 py-2.5 text-[14px] font-medium text-[var(--color-obsidian)]/85 transition hover:bg-[var(--color-powder)] hover:text-[var(--color-obsidian)]"
    >
      {t(item.labelKey)}
    </Link>
  );
}

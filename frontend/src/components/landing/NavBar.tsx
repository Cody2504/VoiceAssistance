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
  Clapperboard,
  Megaphone,
  ShieldCheck,
  Car,
  Code2,
  BookOpen,
  Newspaper,
  Users,
  LifeBuoy,
  type LucideIcon,
} from "lucide-react";
import { Logo } from "@/components/brand/Logo";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

/**
 * Marketing top bar, mimicking the TwelveLabs nav (topbar.png):
 *   logo · Platform ▾ · Pricing · Solutions ▾ · Build ▾ · Resources ▾ · Company ▾
 *   · 🌐 · Playground (filled pill) · Talk to sales (outlined pill)
 *
 * Platform / Solutions / Build open mega-menus whose contents mirror, in order:
 *   twelvelabs.io/product/product-overview · /enterprise · /developer-hub
 * Hover- and keyboard-openable. Guest (logged-out) surface only.
 */

interface MenuItem {
  label: string;
  desc?: string;
  to: string;
  icon?: LucideIcon;
  external?: boolean;
}
interface MenuGroup {
  heading?: string;
  items: MenuItem[];
}
interface NavEntry {
  label: string;
  to?: string;
  groups?: MenuGroup[];
  /** mega = wide multi-column panel; list = narrow single column */
  variant?: "mega" | "list";
}

const NAV: NavEntry[] = [
  {
    label: "Platform",
    variant: "mega",
    groups: [
      {
        heading: "Platform",
        items: [
          { label: "Platform Overview", desc: "Search, analyze & segment video", to: "/product/product-overview", icon: Boxes },
          { label: "Models", desc: "Our encoder + VLM, benchmarked", to: "/product/product-overview#models", icon: Sparkles },
        ],
      },
      {
        heading: "Capabilities",
        items: [
          { label: "Search", desc: "Find any scene in natural language", to: "/product/product-overview", icon: Search },
          { label: "Analyze", desc: "Summaries, chapters, Q&A", to: "/product/product-overview", icon: Sparkles },
          { label: "Segment", desc: "Labeled, time-stamped chapters", to: "/product/product-overview", icon: Layers },
        ],
      },
    ],
  },
  { label: "Pricing", to: "/pricing" },
  {
    label: "Solutions",
    variant: "mega",
    groups: [
      {
        heading: "By industry",
        items: [
          { label: "Media & Entertainment", desc: "Archive search, clip generation", to: "/solutions/media-and-entertainment", icon: Clapperboard },
          { label: "Advertising", desc: "Contextual ad matching", to: "/solutions/advertising", icon: Megaphone },
          { label: "Government & Security", desc: "Evidence & anomaly detection", to: "/solutions/government-and-security", icon: ShieldCheck },
          { label: "Automotive", desc: "Scene understanding at scale", to: "/solutions/automotive", icon: Car },
        ],
      },
      {
        heading: "Enterprise",
        items: [
          { label: "Overview", desc: "Video AI for enterprises", to: "/solutions", icon: Boxes },
          { label: "Case Studies", desc: "Real-world results", to: "/solutions#cases", icon: Newspaper },
          { label: "Security", desc: "Secure by design", to: "/solutions#security", icon: ShieldCheck },
        ],
      },
    ],
  },
  { label: "Build", to: "/build" },
  {
    label: "Resources",
    variant: "list",
    groups: [
      {
        items: [
          { label: "Blog", to: "/#tutorials", icon: Newspaper },
          { label: "Tutorials", to: "/#tutorials", icon: BookOpen },
          { label: "Docs", to: "/build", icon: Code2 },
        ],
      },
    ],
  },
  {
    label: "Company",
    variant: "list",
    groups: [
      {
        items: [
          { label: "About", to: "/", icon: Users },
          { label: "Careers", to: "/", icon: Users },
          { label: "Contact", to: "/#cta", icon: LifeBuoy },
        ],
      },
    ],
  },
];

const LANGS = [
  { code: "en", label: "English" },
  { code: "vi", label: "Tiếng Việt" },
];

export function NavBar() {
  const { user } = useAuth();
  const { i18n } = useTranslation();
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
        <Link to="/" className={cn("shrink-0", isDarkHome && "text-[#f4f2ea]")} aria-label="Jockey">
          <Logo size="sm" />
        </Link>

        {/* center nav */}
        <nav className="hidden items-center gap-1 lg:flex" onMouseLeave={scheduleClose}>
          {NAV.map((entry) =>
            entry.groups ? (
              <div
                key={entry.label}
                className="relative"
                onMouseEnter={() => openMenu(entry.label)}
              >
                <button
                  type="button"
                  aria-expanded={open === entry.label}
                  aria-haspopup="true"
                  onFocus={() => openMenu(entry.label)}
                  onClick={() => setOpen(open === entry.label ? null : entry.label)}
                  className={cn(
                    "inline-flex cursor-pointer items-center gap-1 rounded-lg px-3 py-2 text-[14px] transition",
                    isDarkHome
                      ? open === entry.label
                        ? "text-white"
                        : "text-white/72 hover:text-white"
                      : open === entry.label
                        ? "text-[var(--color-obsidian)]"
                        : "text-[var(--color-obsidian)]/80 hover:text-[var(--color-obsidian)]"
                  )}
                >
                  {entry.label}
                  <ChevronDown
                    size={14}
                    className={cn("transition-transform", open === entry.label && "rotate-180")}
                  />
                </button>

                {open === entry.label && (
                  <MegaPanel entry={entry} onNavigate={() => setOpen(null)} />
                )}
              </div>
            ) : (
              <Link
                key={entry.label}
                to={entry.to!}
                className={cn(
                  "rounded-lg px-3 py-2 text-[14px] transition",
                  isDarkHome
                    ? "text-white/72 hover:text-white"
                    : "text-[var(--color-obsidian)]/80 hover:text-[var(--color-obsidian)]"
                )}
              >
                {entry.label}
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
              aria-label="Select language"
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
            {langOpen && (
              <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-[0_20px_50px_-25px_rgba(0,0,0,0.4)]">
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
            )}
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
              Open app ↗
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
                Playground ↗
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
                Talk to sales ↗
              </a>
            </>
          )}
        </div>
      </div>

      {/* hovering over a menu's panel keeps it open */}
    </header>
  );
}

function MegaPanel({ entry, onNavigate }: { entry: NavEntry; onNavigate: () => void }) {
  const isMega = entry.variant === "mega";
  return (
    <div
      className={cn(
        "absolute left-0 top-full z-50 mt-1 rounded-2xl border border-[var(--color-chalk)] bg-white p-3 shadow-[0_30px_80px_-35px_rgba(0,0,0,0.45)]",
        isMega ? "w-[560px]" : "w-56"
      )}
    >
      <div className={cn("grid gap-x-3 gap-y-1", isMega ? "grid-cols-2" : "grid-cols-1")}>
        {entry.groups!.map((group, gi) => (
          <div key={gi}>
            {group.heading && (
              <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">
                {group.heading}
              </p>
            )}
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.label + item.to}
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
                    <span className="block text-[14px] font-medium text-[var(--color-obsidian)]">
                      {item.label}
                    </span>
                    {item.desc && (
                      <span className="block text-[12px] leading-snug text-[var(--color-gravel)]">
                        {item.desc}
                      </span>
                    )}
                  </span>
                </Link>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

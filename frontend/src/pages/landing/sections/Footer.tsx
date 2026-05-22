import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";

import { Logo } from "@/components/brand/Logo";

function LangSwitch() {
  const { i18n: i18nx, t } = useTranslation();
  const current = i18nx.language?.startsWith("vi") ? "vi" : "en";
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-[var(--color-chalk)] bg-white p-1 text-xs">
      {(["en", "vi"] as const).map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => i18n.changeLanguage(code)}
          className={
            "rounded-full px-2.5 py-1 transition " +
            (current === code
              ? "bg-[var(--color-obsidian)] text-white"
              : "text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]")
          }
        >
          {t(`lang.${code}`)}
        </button>
      ))}
    </div>
  );
}

const LINKS = [
  {
    label: "Platform",
    items: [
      { name: "Search", to: "/playground/search" },
      { name: "Analyze", to: "/playground/analyze" },
      { name: "Segment", to: "/playground/segment" },
      { name: "Examples", to: "/examples" },
    ],
  },
  {
    label: "Resources",
    items: [
      { name: "Pricing", to: "/pricing" },
      { name: "API Docs", to: "#" },
      { name: "Tutorials", to: "#tutorials" },
      { name: "Research", to: "#" },
    ],
  },
  {
    label: "Company",
    items: [
      { name: "About", to: "#" },
      { name: "Contact", to: "#" },
      { name: "Privacy", to: "#" },
      { name: "Terms", to: "#" },
    ],
  },
];

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-[var(--color-chalk)] bg-[var(--color-eggshell)]">
      <div className="mx-auto grid max-w-[1200px] gap-10 px-6 py-16 md:grid-cols-[1.4fr_repeat(3,minmax(0,1fr))]">
        <div>
          <Link to="/" aria-label="Jockey"><Logo size="md" /></Link>
          <p className="mt-4 max-w-[280px] text-[13px] leading-[1.55] text-[var(--color-gravel)]">
            Video-native AI for search, analysis and segmentation — built on open ViCLIP and
            QD-DETR models.
          </p>
        </div>
        {LINKS.map((col) => (
          <div key={col.label}>
            <h4 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--color-gravel)]">
              {col.label}
            </h4>
            <ul className="mt-4 space-y-2.5 text-[13px] text-[var(--color-obsidian)]">
              {col.items.map((i) => (
                <li key={i.name}>
                  <Link to={i.to} className="hover:opacity-70 transition">
                    {i.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-[var(--color-chalk)]">
        <div className="mx-auto flex max-w-[1200px] flex-col items-start gap-3 px-6 py-5 text-[12px] text-[var(--color-slate)] md:flex-row md:items-center md:justify-between">
          <span>© {year} Jockey. Built with open models.</span>
          <LangSwitch />
        </div>
      </div>
    </footer>
  );
}

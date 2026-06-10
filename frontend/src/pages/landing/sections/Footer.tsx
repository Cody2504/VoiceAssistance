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
    headingKey: "footer.col.platform",
    items: [
      { nameKey: "footer.links.platform_overview", to: "/product/product-overview" },
      { nameKey: "footer.links.models", to: "/product/product-overview#models" },
      { nameKey: "footer.links.pricing", to: "/pricing" },
      { nameKey: "footer.links.examples", to: "/examples" },
    ],
  },
  {
    headingKey: "footer.col.solutions",
    items: [
      { nameKey: "footer.links.media_entertainment", to: "/solutions/media-and-entertainment" },
      { nameKey: "footer.links.advertising", to: "/solutions/advertising" },
      { nameKey: "footer.links.government_security", to: "/solutions/government-and-security" },
      { nameKey: "footer.links.automotive", to: "/solutions/automotive" },
    ],
  },
  {
    headingKey: "footer.col.developers",
    items: [
      { nameKey: "footer.links.developer_hub", to: "/build" },
      { nameKey: "footer.links.api_docs", to: "/build#api" },
      { nameKey: "footer.links.sdks", to: "/build#sdks" },
      { nameKey: "footer.links.sample_apps", to: "/build#samples" },
    ],
  },
  {
    headingKey: "footer.col.company",
    items: [
      { nameKey: "footer.links.about", to: "/solutions" },
      { nameKey: "footer.links.contact", to: "/#cta" },
    ],
  },
];

export function Footer() {
  const { t } = useTranslation();
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-[var(--color-chalk)] bg-[var(--color-eggshell)]">
      <div className="mx-auto grid max-w-[1200px] gap-10 px-6 py-16 md:grid-cols-[1.4fr_repeat(4,minmax(0,1fr))]">
        <div>
          <Link to="/" aria-label="Jockey"><Logo size="md" /></Link>
          <p className="mt-4 max-w-[280px] text-[13px] leading-[1.55] text-[var(--color-gravel)]">
            {t("footer.tagline")}
          </p>
        </div>
        {LINKS.map((col) => (
          <div key={col.headingKey}>
            <h4 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--color-gravel)]">
              {t(col.headingKey)}
            </h4>
            <ul className="mt-4 space-y-2.5 text-[13px] text-[var(--color-obsidian)]">
              {col.items.map((i) => (
                <li key={i.nameKey}>
                  <Link to={i.to} className="hover:opacity-70 transition">
                    {t(i.nameKey)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-[var(--color-chalk)]">
        <div className="mx-auto flex max-w-[1200px] flex-col items-start gap-3 px-6 py-5 text-[12px] text-[var(--color-slate)] md:flex-row md:items-center md:justify-between">
          <span>{t("footer.copyright", { year })}</span>
          <LangSwitch />
        </div>
      </div>
    </footer>
  );
}

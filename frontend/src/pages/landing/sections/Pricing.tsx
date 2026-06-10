import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Tier {
  nameKey: string;
  priceKey: string;
  cadenceKey?: string;
  blurbKey: string;
  cta: { labelKey: string; to: string };
  featureKeys: string[];
  highlight?: boolean;
}

const TIERS: Tier[] = [
  {
    nameKey: "landing.pricing.free_name",
    priceKey: "landing.pricing.free_price",
    cadenceKey: "landing.pricing.free_cadence",
    blurbKey: "landing.pricing.free_blurb",
    cta: { labelKey: "landing.pricing.free_cta", to: "/signup" },
    featureKeys: [
      "landing.pricing.free_f1",
      "landing.pricing.free_f2",
      "landing.pricing.free_f3",
      "landing.pricing.free_f4",
    ],
  },
  {
    nameKey: "landing.pricing.dev_name",
    priceKey: "landing.pricing.dev_price",
    blurbKey: "landing.pricing.dev_blurb",
    cta: { labelKey: "landing.pricing.dev_cta", to: "/pricing" },
    featureKeys: [
      "landing.pricing.dev_f1",
      "landing.pricing.dev_f2",
      "landing.pricing.dev_f3",
      "landing.pricing.dev_f4",
    ],
    highlight: true,
  },
  {
    nameKey: "landing.pricing.ent_name",
    priceKey: "landing.pricing.ent_price",
    blurbKey: "landing.pricing.ent_blurb",
    cta: { labelKey: "landing.pricing.ent_cta", to: "/pricing" },
    featureKeys: [
      "landing.pricing.ent_f1",
      "landing.pricing.ent_f2",
      "landing.pricing.ent_f3",
      "landing.pricing.ent_f4",
    ],
  },
];

export function Pricing() {
  const { t } = useTranslation();
  return (
    <section id="pricing" className="mx-auto max-w-[1200px] px-6 py-24">
      <header className="mb-12 text-center">
        <h2 className="text-[40px] font-light leading-[1.06] tracking-[-1px] text-[var(--color-obsidian)] md:text-[48px]">
          {t("landing.pricing.h2_line1")}
          <br />
          {t("landing.pricing.h2_line2")}
        </h2>
        <p className="mx-auto mt-5 max-w-[560px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          {t("landing.pricing.sub")}
        </p>
      </header>

      <div className="grid gap-5 md:grid-cols-3">
        {TIERS.map((tier) => (
          <div
            key={tier.nameKey}
            className={cn(
              "flex flex-col rounded-[24px] border border-[var(--color-chalk)] bg-white p-7 shadow-hairline transition-all",
              tier.highlight && "border-[var(--color-obsidian)]",
            )}
          >
            <h3 className="text-[16px] font-medium text-[var(--color-obsidian)]">{t(tier.nameKey)}</h3>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="text-[32px] font-light tracking-[-0.6px] text-[var(--color-obsidian)]">
                {t(tier.priceKey)}
              </span>
              {tier.cadenceKey && (
                <span className="text-[13px] text-[var(--color-gravel)]">{t(tier.cadenceKey)}</span>
              )}
            </div>
            <p className="mt-3 text-[13px] leading-[1.5] text-[var(--color-gravel)]">{t(tier.blurbKey)}</p>
            <Link
              to={tier.cta.to}
              className={cn(
                "mt-6 inline-flex h-10 items-center justify-center rounded-full px-5 text-[13px] font-medium transition",
                tier.highlight
                  ? "bg-[var(--color-obsidian)] text-white hover:bg-neutral-800"
                  : "border border-[var(--color-chalk)] bg-white text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
              )}
            >
              {t(tier.cta.labelKey)}
            </Link>
            <ul className="mt-7 space-y-2.5 text-[13px] leading-[1.5] text-[var(--color-obsidian)]/80">
              {tier.featureKeys.map((fk) => (
                <li key={fk} className="flex items-start gap-2">
                  <Check size={14} className="mt-0.5 shrink-0 text-[var(--color-obsidian)]/60" />
                  {t(fk)}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

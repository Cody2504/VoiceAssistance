import { Link } from "react-router";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Tier {
  name: string;
  price: string;
  cadence?: string;
  blurb: string;
  cta: { label: string; to: string };
  features: string[];
  highlight?: boolean;
}

const TIERS: Tier[] = [
  {
    name: "Free",
    price: "$0",
    cadence: "/ month",
    blurb: "Kick the tires. Index and search up to 10 hours of video.",
    cta: { label: "Get started", to: "/signup" },
    features: ["10 hours of video / month", "1 default index", "Search, Analyze, Segment", "Community support"],
  },
  {
    name: "Developer",
    price: "Pay as you go",
    blurb: "Scale ingest and queries with usage-based pricing.",
    cta: { label: "Upgrade", to: "/pricing" },
    features: ["Per-minute ingest + per-query pricing", "Unlimited indexes", "API keys + webhooks", "Priority email support"],
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    blurb: "Dedicated capacity, SSO, and white-glove onboarding.",
    cta: { label: "Talk to sales", to: "/pricing" },
    features: ["Dedicated infra + SLAs", "SAML / SSO + audit logs", "Private deployment options", "Solutions engineering"],
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="mx-auto max-w-[1200px] px-6 py-24">
      <header className="mb-12 text-center">
        <h2 className="text-[40px] font-light leading-[1.06] tracking-[-1px] text-[var(--color-obsidian)] md:text-[48px]">
          Play for free.
          <br />
          Pay as you go.
        </h2>
        <p className="mx-auto mt-5 max-w-[560px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          Start free and only pay for what you use. No surprises, no commitments.
        </p>
      </header>

      <div className="grid gap-5 md:grid-cols-3">
        {TIERS.map((t) => (
          <div
            key={t.name}
            className={cn(
              "flex flex-col rounded-[24px] border border-[var(--color-chalk)] bg-white p-7 shadow-hairline transition-all",
              t.highlight && "border-[var(--color-obsidian)]",
            )}
          >
            <h3 className="text-[16px] font-medium text-[var(--color-obsidian)]">{t.name}</h3>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="text-[32px] font-light tracking-[-0.6px] text-[var(--color-obsidian)]">
                {t.price}
              </span>
              {t.cadence && (
                <span className="text-[13px] text-[var(--color-gravel)]">{t.cadence}</span>
              )}
            </div>
            <p className="mt-3 text-[13px] leading-[1.5] text-[var(--color-gravel)]">{t.blurb}</p>
            <Link
              to={t.cta.to}
              className={cn(
                "mt-6 inline-flex h-10 items-center justify-center rounded-full px-5 text-[13px] font-medium transition",
                t.highlight
                  ? "bg-[var(--color-obsidian)] text-white hover:bg-neutral-800"
                  : "border border-[var(--color-chalk)] bg-white text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
              )}
            >
              {t.cta.label}
            </Link>
            <ul className="mt-7 space-y-2.5 text-[13px] leading-[1.5] text-[var(--color-obsidian)]/80">
              {t.features.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <Check size={14} className="mt-0.5 shrink-0 text-[var(--color-obsidian)]/60" />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

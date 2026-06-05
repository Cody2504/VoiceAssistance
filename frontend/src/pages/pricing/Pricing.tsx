import { useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, Plus, Minus, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

import {
  FAMILIES,
  ITEMS,
  TIERS,
  COMPARISON,
  FAQS,
  type FamilyId,
  type TierId,
} from "./pricingData";

const HORSE_GLYPH = (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden>
    <path d="M19 6c0-.55-.45-1-1-1h-2l-1-1H9L8 5H6c-.55 0-1 .45-1 1v.5c0 1.66 1.34 3 3 3h.5l-.5 2-3 1.5L3 14v3l3.5-.5L9 14h.5l.5 1.5L9 19h2l1.5-3 1.5 3h2l-1-3.5.5-1.5h3l-.5-2 .5-2c1.1 0 2-.9 2-2V6z" />
  </svg>
);

function priceLabel(tier: TierId, item: (typeof ITEMS)[number]): string {
  if (tier === "free") return item.freeMonthly === "—" ? "—" : "Free";
  if (tier === "enterprise") return "Custom";
  return `$${item.developerRate} ${item.unitShort}`;
}

function FamilyCard({ family }: { family: (typeof FAMILIES)[FamilyId] }) {
  return (
    <div
      className={`relative overflow-hidden rounded-3xl bg-gradient-to-br ${family.gradientClass} p-7 md:p-9`}
    >
      <div className="flex items-start gap-5">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/40 ring-1 ring-white/60 backdrop-blur">
          <span className="text-[var(--ink)]">{HORSE_GLYPH}</span>
        </div>
        <div>
          <h3 className="text-2xl font-semibold tracking-tight text-[var(--ink)]">{family.name}</h3>
          <p className="mt-3 max-w-[52ch] text-sm leading-relaxed text-[var(--ink-soft)]">
            {family.tagline}
          </p>
        </div>
      </div>
    </div>
  );
}

function TierCard({ tier }: { tier: (typeof TIERS)[number] }) {
  const eclipseItems = ITEMS.filter((i) => i.family === "eclipse");
  const secretariatItems = ITEMS.filter((i) => i.family === "secretariat");

  return (
    <div
      className={`flex flex-col rounded-3xl border border-[var(--line)] ${tier.accentClass} p-7 transition`}
    >
      <div>
        <h3 className="text-3xl font-semibold tracking-tight text-[var(--ink)]">{tier.name}</h3>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">{tier.subtitle}</p>
      </div>

      <Link
        to={tier.cta.href}
        className="mt-6 inline-flex h-10 w-fit items-center gap-1.5 rounded-full bg-[var(--ink)] px-5 text-sm font-semibold text-white transition duration-150 ease-out hover:bg-black active:scale-[0.97]"
      >
        {tier.cta.label}
        <ArrowUpRight className="h-3.5 w-3.5" />
      </Link>

      {/* Eclipse section */}
      <div className="mt-8 border-t border-[var(--line)] pt-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
          <span className="text-[var(--ink-soft)]">{HORSE_GLYPH}</span>
          {FAMILIES.eclipse.name}
        </div>
        <ul className="mt-4 space-y-3">
          {eclipseItems.map((item) => (
            <li key={item.id} className="flex items-baseline justify-between gap-2 text-sm">
              <span className="text-[var(--ink-soft)]">{item.label}</span>
              <span className="font-medium text-[var(--ink)]">{priceLabel(tier.id, item)}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Secretariat section */}
      <div className="mt-8 border-t border-[var(--line)] pt-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
          <span className="text-[var(--ink-soft)]">{HORSE_GLYPH}</span>
          {FAMILIES.secretariat.name}
        </div>
        <ul className="mt-4 space-y-3">
          {secretariatItems.map((item) => (
            <li key={item.id} className="flex items-baseline justify-between gap-2 text-sm">
              <span className="text-[var(--ink-soft)]">{item.label}</span>
              <span className="font-medium text-[var(--ink)]">{priceLabel(tier.id, item)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ComparisonTable() {
  return (
    <div className="mt-12 overflow-hidden rounded-2xl border border-[var(--line)] bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-[var(--bg)] text-[var(--ink-soft)]">
          <tr>
            <th className="px-6 py-3 font-medium">Compare plans</th>
            {TIERS.map((t) => (
              <th key={t.id} className="px-6 py-3 font-medium">
                {t.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COMPARISON.map((row, i) => (
            <tr
              key={row.label}
              className={i % 2 === 0 ? "bg-white" : "bg-[var(--bg)]/60"}
            >
              <td className="px-6 py-3.5 text-[var(--ink)]">{row.label}</td>
              <td className="px-6 py-3.5 text-[var(--ink-soft)]">{row.free}</td>
              <td className="px-6 py-3.5 text-[var(--ink-soft)]">{row.developer}</td>
              <td className="px-6 py-3.5 text-[var(--ink-soft)]">{row.enterprise}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[var(--line)]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 py-5 text-left text-[var(--ink)] transition hover:text-black"
        aria-expanded={open}
      >
        <span className="text-sm font-medium md:text-base">{q}</span>
        <span className="shrink-0 text-[var(--ink-soft)]">
          {open ? <Minus className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
        </span>
      </button>
      {/* grid-rows 0fr→1fr animates the answer height smoothly (no snap) */}
      <div
        className={cn(
          "grid transition-all duration-300 ease-out",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        )}
      >
        <div className="overflow-hidden">
          <p className="pb-5 pr-8 text-sm leading-relaxed text-[var(--ink-soft)]">{a}</p>
        </div>
      </div>
    </div>
  );
}

export default function Pricing() {
  return (
    <main className="mx-auto max-w-6xl px-6 pb-24">
      {/* Hero */}
      <section className="fade-rise pt-16 text-center md:pt-24">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-white/60 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--ink-soft)] backdrop-blur">
          <Sparkles className="h-3 w-3 text-[var(--accent)]" />
          Pricing
        </span>
        <h1 className="mt-5 text-[40px] font-semibold leading-[1.05] tracking-[-0.02em] md:text-[56px]">
          Start free, <span className="gradient-text">speed up</span>, or scale.
        </h1>
        <p className="mx-auto mt-5 max-w-[52ch] text-base leading-relaxed text-[var(--ink-soft)]">
          Build, launch, and grow with flexible plans that match your momentum. Pay only for what
          you use and change course at any time.
        </p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/pricing-calculator"
            className="inline-flex h-11 items-center gap-1.5 rounded-full bg-[var(--ink)] px-6 text-sm font-semibold text-white transition duration-150 ease-out hover:bg-black active:scale-[0.97]"
          >
            Pricing Calculator
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </section>

      {/* Model family cards */}
      <section className="mt-16 grid gap-5 md:mt-20 md:grid-cols-2">
        <FamilyCard family={FAMILIES.eclipse} />
        <FamilyCard family={FAMILIES.secretariat} />
      </section>

      {/* Tier cards */}
      <section className="mt-16 md:mt-20">
        <div className="grid gap-5 md:grid-cols-3">
          {TIERS.map((t) => (
            <TierCard key={t.id} tier={t} />
          ))}
        </div>
        <p className="mt-6 text-center text-xs text-[var(--ink-muted)]">
          Rate limits apply and scale with monthly spend. See details in our API docs.
        </p>
      </section>

      {/* Comparison */}
      <section id="compare" className="mt-20 scroll-mt-24">
        <h2 className="text-center text-2xl font-semibold tracking-tight md:text-3xl">
          Compare plans side-by-side
        </h2>
        <ComparisonTable />
      </section>

      {/* FAQ */}
      <section className="mt-24">
        <h2 className="text-center text-3xl font-semibold tracking-tight md:text-[40px]">
          Fast answers to frequent questions.
        </h2>
        <div className="mx-auto mt-10 grid max-w-5xl gap-x-12 md:grid-cols-2">
          <div>
            {FAQS.slice(0, Math.ceil(FAQS.length / 2)).map((f) => (
              <FAQItem key={f.q} q={f.q} a={f.a} />
            ))}
          </div>
          <div>
            {FAQS.slice(Math.ceil(FAQS.length / 2)).map((f) => (
              <FAQItem key={f.q} q={f.q} a={f.a} />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

import { Link } from "react-router";
import {
  Clapperboard,
  Megaphone,
  ShieldCheck,
  Car,
  Landmark,
  Sparkles,
  Lock,
  Server,
  KeyRound,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Footer } from "@/pages/landing/sections/Footer";

/**
 * Solutions page — mirrors twelvelabs.io/enterprise:
 * hero · industries · stats band · case studies · secure-by-design ·
 * partners · final CTA. Light theme, guest-facing, no backend.
 */

function Section({ id, children, className = "" }: { id?: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={`mx-auto max-w-[1200px] px-6 ${className}`}>
      {children}
    </section>
  );
}

export default function Solutions() {
  const { t } = useTranslation();

  const INDUSTRIES = [
    { icon: Clapperboard, titleKey: "marketing.solutions.industries.media_title",       bodyKey: "marketing.solutions.industries.media_body",       tone: "bg-[#fbdfff]", ink: "text-[#5e3b66]" },
    { icon: Megaphone,    titleKey: "marketing.solutions.industries.advertising_title", bodyKey: "marketing.solutions.industries.advertising_body", tone: "bg-[#fde3a2]", ink: "text-[#7d5d0c]" },
    { icon: ShieldCheck,  titleKey: "marketing.solutions.industries.gov_title",         bodyKey: "marketing.solutions.industries.gov_body",         tone: "bg-[#c4eefe]", ink: "text-[#26586d]" },
    { icon: Car,          titleKey: "marketing.solutions.industries.auto_title",        bodyKey: "marketing.solutions.industries.auto_body",        tone: "bg-[#d9f5dd]", ink: "text-[#2f6b3a]" },
    { icon: Landmark,     titleKey: "marketing.solutions.industries.public_title",      bodyKey: "marketing.solutions.industries.public_body",      tone: "bg-[#e7e3ff]", ink: "text-[#4a3b8c]" },
    { icon: Sparkles,     titleKey: "marketing.solutions.industries.creative_title",    bodyKey: "marketing.solutions.industries.creative_body",    tone: "bg-[#ffe1d6]", ink: "text-[#8a4326]" },
  ];

  const STATS = [
    { valueKey: "marketing.solutions.stats.accuracy_value", labelKey: "marketing.solutions.stats.accuracy_label" },
    { valueKey: "marketing.solutions.stats.speed_value",    labelKey: "marketing.solutions.stats.speed_label" },
    { valueKey: "marketing.solutions.stats.index_value",    labelKey: "marketing.solutions.stats.index_label" },
  ];

  const CASES = [
    { tagKey: "marketing.solutions.cases.sports_tag",    titleKey: "marketing.solutions.cases.sports_title",    bodyKey: "marketing.solutions.cases.sports_body" },
    { tagKey: "marketing.solutions.cases.broadcast_tag", titleKey: "marketing.solutions.cases.broadcast_title", bodyKey: "marketing.solutions.cases.broadcast_body" },
    { tagKey: "marketing.solutions.cases.adtech_tag",    titleKey: "marketing.solutions.cases.adtech_title",    bodyKey: "marketing.solutions.cases.adtech_body" },
  ];

  const SECURITY = [
    { icon: Lock,     titleKey: "marketing.solutions.security.encrypted_title", bodyKey: "marketing.solutions.security.encrypted_body" },
    { icon: Server,   titleKey: "marketing.solutions.security.deploy_title",    bodyKey: "marketing.solutions.security.deploy_body" },
    { icon: KeyRound, titleKey: "marketing.solutions.security.sso_title",       bodyKey: "marketing.solutions.security.sso_body" },
  ];

  return (
    <main className="bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
      {/* hero */}
      <Section className="pt-20 pb-14 text-center md:pt-24">
        <p className="mb-5 text-[13px] uppercase tracking-[0.18em] text-[var(--color-gravel)]">
          {t("marketing.solutions.hero_eyebrow")}
        </p>
        <h1 className="mx-auto max-w-[900px] text-[44px] font-light leading-[1.05] tracking-[-1.2px] text-[var(--color-obsidian)] md:text-[60px]">
          {t("marketing.solutions.hero_heading")}
        </h1>
        <p className="mx-auto mt-6 max-w-[640px] text-[16px] leading-[1.55] text-[var(--color-gravel)] md:text-[17px]">
          {t("marketing.solutions.hero_sub")}
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <a href="/#cta" className="inline-flex h-11 cursor-pointer items-center rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]">
            {t("marketing.solutions.talk_to_sales")}
          </a>
          <Link to="/signup" className="inline-flex h-11 cursor-pointer items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]">
            {t("marketing.solutions.start_free")}
          </Link>
        </div>
      </Section>

      {/* industries */}
      <Section id="industries" className="py-16">
        <h2 className="text-center text-[30px] font-light tracking-[-0.6px] md:text-[38px]">
          {t("marketing.solutions.industries_heading")}
        </h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {INDUSTRIES.map((it) => {
            const Icon = it.icon;
            return (
              <div key={it.titleKey} className={`rounded-[20px] ${it.tone} p-6`}>
                <span className={`inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white/70 ${it.ink}`}>
                  <Icon size={20} />
                </span>
                <h3 className={`mt-4 text-[18px] font-semibold ${it.ink}`}>{t(it.titleKey)}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-obsidian)]/70">{t(it.bodyKey)}</p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* stats band */}
      <Section className="py-16">
        <div className="grid gap-8 rounded-[24px] border border-[var(--color-chalk)] bg-white p-10 sm:grid-cols-3">
          {STATS.map((s) => (
            <div key={s.valueKey} className="text-center">
              <div className="text-[44px] font-light tabular-nums tracking-[-1px] text-[var(--color-obsidian)]">{t(s.valueKey)}</div>
              <p className="mt-2 text-[13px] leading-snug text-[var(--color-gravel)]">{t(s.labelKey)}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* case studies */}
      <Section id="cases" className="py-16">
        <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.solutions.cases_heading")}</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {CASES.map((c) => (
            <div key={c.titleKey} className="rounded-[20px] border border-[var(--color-chalk)] bg-white p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">{t(c.tagKey)}</p>
              <h3 className="mt-2 text-[18px] font-semibold">{t(c.titleKey)}</h3>
              <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{t(c.bodyKey)}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* secure by design */}
      <Section id="security" className="py-16">
        <div className="rounded-[24px] bg-[var(--color-powder)] p-10">
          <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.solutions.secure_heading")}</h2>
          <p className="mt-2 max-w-[640px] text-[15px] text-[var(--color-gravel)]">
            {t("marketing.solutions.secure_sub")}
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {SECURITY.map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.titleKey} className="rounded-[18px] border border-[var(--color-chalk)] bg-white p-6">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
                    <Icon size={20} />
                  </span>
                  <h3 className="mt-4 text-[16px] font-semibold">{t(s.titleKey)}</h3>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{t(s.bodyKey)}</p>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      {/* final CTA */}
      <Section className="py-20 text-center">
        <h2 className="mx-auto max-w-[760px] text-[34px] font-light tracking-[-0.8px] md:text-[46px]">
          {t("marketing.solutions.cta_heading")}
        </h2>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/signup" className="inline-flex h-11 cursor-pointer items-center rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]">
            {t("marketing.solutions.start_free_cta")}
          </Link>
          <a href="/#cta" className="inline-flex h-11 cursor-pointer items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]">
            {t("marketing.solutions.talk_to_sales")}
          </a>
        </div>
      </Section>

      <Footer />
    </main>
  );
}

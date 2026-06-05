import { Fragment } from "react";
import { Link } from "react-router";
import { Check, ArrowUpRight, Sparkles } from "lucide-react";
import { Footer } from "@/pages/landing/sections/Footer";
import { cn } from "@/lib/utils";
import {
  VALUE_PILLARS,
  VALUE_HEADING,
  VALUE_SUB,
  PRICING_TIERS,
  PRICING_SUB,
  type IndustryData,
} from "./industryData";

/**
 * Template for the four industry solution pages, mirroring the section flow of
 * twelvelabs.io/solutions/*:
 *   hero (split row + stadium cover) · numbered feature tiles · use cases ·
 *   value pillars · pricing · final CTA.
 * Industry copy comes via `data`; value pillars and pricing are shared.
 * Guest-facing, light eggshell skin, no backend.
 */

function Section({ id, children, className = "" }: { id?: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={cn("mx-auto max-w-[1200px] px-6", className)}>
      {children}
    </section>
  );
}

/** Bordered uppercase chip used for eyebrows and the numbered tiles. */
function Chip({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[8px] border border-[var(--color-obsidian)] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--color-obsidian)]",
        className
      )}
    >
      {children}
    </span>
  );
}

/** Thin vertical divider shown between columns on md+ (matches the framer rows). */
function VDivider() {
  return <div aria-hidden className="hidden w-px shrink-0 self-stretch bg-[var(--color-chalk)] md:block" />;
}

export default function SolutionPage({ data }: { data: IndustryData }) {
  return (
    <main className="bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
      {/* ---------- hero ---------- */}
      <Section className="pt-14 md:pt-20">
        <div className="grid gap-8 border-b border-[var(--color-chalk)] pb-10 md:grid-cols-[1.25fr_0.75fr] md:gap-12 md:pb-14">
          <div>
            <Chip>{data.eyebrow}</Chip>
            <h1 className="mt-6 whitespace-pre-line text-[38px] font-light leading-[1.04] tracking-[-1px] md:text-[50px]">
              {data.heroTitle}
            </h1>
          </div>
          <div className="flex flex-col justify-center md:border-l md:border-[var(--color-chalk)] md:pl-10">
            <p className="max-w-[440px] text-[16px] leading-[1.55] text-[var(--color-gravel)] md:text-[17px]">
              {data.heroSub}
            </p>
            <div className="mt-7">
              <a
                href="#cta"
                className="inline-flex h-12 items-center gap-2 rounded-[18px] bg-[var(--color-obsidian)] px-6 text-[15px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]"
              >
                Talk to Sales
              </a>
            </div>
          </div>
        </div>

        {/* stadium-rounded cover */}
        <div className="mt-8 overflow-hidden rounded-[48px] md:mt-12 md:rounded-[120px]" style={{ aspectRatio: "16 / 9" }}>
          {data.media.type === "video" ? (
            <video
              src={data.media.src}
              poster={data.media.poster}
              autoPlay
              muted
              loop
              playsInline
              className="h-full w-full object-cover"
            />
          ) : (
            <img src={data.media.src} alt={`${data.eyebrow} video intelligence`} loading="lazy" className="h-full w-full object-cover" />
          )}
        </div>
      </Section>

      {/* ---------- numbered feature tiles ---------- */}
      <Section className="py-14 md:py-20">
        <div className="flex flex-col gap-12 md:flex-row md:gap-0">
          {data.features.map((f, i) => (
            <Fragment key={f.n}>
              {i > 0 && <VDivider />}
              <div className="flex-1 md:px-7 md:first:pl-0 md:last:pr-0">
                <div className={cn("relative overflow-hidden rounded-[40px]", data.tone)} style={{ aspectRatio: "16 / 9" }}>
                  <img src={f.image} alt="" loading="lazy" className="h-full w-full object-cover" />
                  {f.caption && (
                    <span className="absolute left-4 top-4 inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-obsidian)] shadow-[0_8px_24px_-12px_rgba(0,0,0,0.5)] backdrop-blur">
                      <Sparkles size={12} className="text-[var(--color-accent-blue)]" />
                      {f.caption}
                    </span>
                  )}
                </div>
                <div className="mt-6">
                  <Chip className="px-2 py-0.5">{f.n}</Chip>
                </div>
                <h2 className="mt-4 text-[24px] font-medium leading-tight tracking-[-0.3px] md:text-[26px]">{f.title}</h2>
                <p className="mt-3 text-[14.5px] leading-relaxed text-[var(--color-gravel)]">{f.body}</p>
              </div>
            </Fragment>
          ))}
        </div>
      </Section>

      {/* ---------- use cases ---------- */}
      <Section className="py-14 md:py-20">
        <div className="text-center">
          <Chip>Use Cases</Chip>
          <h2 className="mx-auto mt-5 max-w-[760px] text-[34px] font-light leading-[1.06] tracking-[-1px] md:text-[46px]">
            {data.useCasesHeading}
          </h2>
        </div>
        <div className="mt-12 flex flex-col gap-10 md:flex-row md:gap-0">
          {data.useCaseGroups.map((g, i) => (
            <Fragment key={g.title}>
              {i > 0 && <VDivider />}
              <div className="flex-1 md:px-8 md:first:pl-0 md:last:pr-0">
                <h3 className="text-[19px] font-medium tracking-[-0.2px]">{g.title}</h3>
                <ul className="mt-6">
                  {g.items.map((item) => (
                    <li key={item} className="border-b border-[var(--color-chalk)] py-3.5 text-[14.5px] text-[var(--color-gravel)]">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </Fragment>
          ))}
        </div>
      </Section>

      {/* ---------- value pillars ---------- */}
      <Section className="py-14 md:py-20">
        <div className="text-center">
          <Chip>Our Value</Chip>
          <h2 className="mx-auto mt-5 max-w-[760px] text-[34px] font-light leading-[1.06] tracking-[-1px] md:text-[46px]">
            {VALUE_HEADING}
          </h2>
          <p className="mx-auto mt-5 max-w-[620px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">{VALUE_SUB}</p>
        </div>
        <div className="mt-12 flex flex-col gap-12 md:mt-16 md:flex-row md:items-stretch md:gap-0">
          {VALUE_PILLARS.map((p, i) => {
            const PillarIcon = p.icon;
            return (
              <Fragment key={p.title}>
                {i > 0 && <VDivider />}
                <div className="flex flex-1 flex-col md:px-8 md:pt-6 md:first:pl-0 md:last:pr-0">
                  <span className="mx-auto flex h-[84px] w-[84px] items-center justify-center rounded-[22px] border border-current text-[var(--color-obsidian)]">
                    <PillarIcon className="h-9 w-9" />
                  </span>
                  <div className="mt-10 md:mt-24">
                    <h3 className="text-[20px] font-medium tracking-[-0.2px]">{p.title}</h3>
                    <p className="mt-2.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{p.body}</p>
                  </div>
                </div>
              </Fragment>
            );
          })}
        </div>
      </Section>

      {/* ---------- pricing ---------- */}
      <Section className="py-14 md:py-20">
        <div className="grid gap-6 border-y border-[var(--color-chalk)] py-10 md:grid-cols-2 md:gap-12">
          <h2 className="text-[32px] font-light leading-[1.04] tracking-[-1px] md:text-[44px]">
            Play for free.
            <br />
            Pay as you go.
          </h2>
          <p className="max-w-[440px] self-center text-[15px] leading-[1.6] text-[var(--color-gravel)] md:border-l md:border-[var(--color-chalk)] md:pl-10">
            {PRICING_SUB}
          </p>
        </div>

        <div className="mt-12 flex flex-col gap-10 md:flex-row md:gap-0">
          {PRICING_TIERS.map((t, i) => (
            <Fragment key={t.name}>
              {i > 0 && <VDivider />}
              <div className="flex-1 md:px-7 md:first:pl-0 md:last:pr-0">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-[22px] font-medium">{t.name}</h3>
                    <p className="mt-1 text-[13.5px] text-[var(--color-gravel)]">{t.description}</p>
                  </div>
                  <Link
                    to={t.to}
                    className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-[14px] border border-[var(--color-obsidian)] px-4 text-[13px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-obsidian)] hover:text-white active:scale-[0.97]"
                  >
                    {t.cta}
                    <ArrowUpRight size={14} />
                  </Link>
                </div>
                <ul className="mt-7">
                  {t.rows.map((r) => (
                    <li
                      key={r.label}
                      className="flex items-center justify-between gap-3 border-b border-[var(--color-chalk)] py-3.5 text-[14px]"
                    >
                      {r.value ? (
                        <>
                          <span className="flex items-center gap-2 text-[var(--color-obsidian)]">
                            <Check size={15} className="shrink-0 text-[var(--color-obsidian)]" />
                            {r.label}
                          </span>
                          <span className="text-[var(--color-gravel)]">{r.value}</span>
                        </>
                      ) : (
                        <span className="pl-[23px] text-[var(--color-slate)]">{r.label}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </Fragment>
          ))}
        </div>

        <p className="mt-8 text-center text-[13px]">
          <Link to="/pricing" className="font-medium text-[var(--color-accent-blue)] hover:underline">
            See full pricing
          </Link>
        </p>
      </Section>

      {/* ---------- final CTA ---------- */}
      <Section id="cta" className="pb-24 pt-10">
        <div className="rounded-[32px] bg-gradient-warm px-8 py-20 text-center md:py-24">
          <h2 className="mx-auto max-w-[720px] text-[34px] font-light leading-[1.05] tracking-[-1px] md:text-[48px]">
            {data.ctaTitle}
          </h2>
          <p className="mx-auto mt-5 max-w-[520px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
            Try your own video in the free Playground, or talk to our team.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/signup"
              className="inline-flex h-11 items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]"
            >
              Try on Playground
              <ArrowUpRight size={16} />
            </Link>
            <Link
              to="/pricing"
              className="inline-flex h-11 items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]"
            >
              Talk to sales
            </Link>
          </div>
        </div>
      </Section>

      <Footer />
    </main>
  );
}

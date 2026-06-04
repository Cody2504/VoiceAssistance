import { useState } from "react";
import { Link } from "react-router";
import { Check, Copy, ArrowUpRight } from "lucide-react";
import { Footer } from "@/pages/landing/sections/Footer";
import {
  VALUE_PILLARS,
  PRICING_TIERS,
  SOLUTION_CODE,
  type IndustryData,
} from "./industryData";

/**
 * Template for the four industry solution pages. Mirrors the section flow of
 * twelvelabs.io/solutions/*: hero · numbered features · use cases · value
 * pillars · code sample · pricing · final CTA. Industry-specific copy comes in
 * via `data`; pillars, code and pricing are shared. Guest-facing, no backend.
 */

function Section({ id, children, className = "" }: { id?: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={`mx-auto max-w-[1200px] px-6 ${className}`}>
      {children}
    </section>
  );
}

export default function SolutionPage({ data }: { data: IndustryData }) {
  const [copied, setCopied] = useState(false);
  const Icon = data.icon;

  function copy() {
    void navigator.clipboard?.writeText(SOLUTION_CODE).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  }

  return (
    <main className="bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
      {/* ---------- hero ---------- */}
      <Section className="pt-16 pb-12 md:pt-20">
        <div className="grid items-center gap-10 lg:grid-cols-[1fr_0.95fr]">
          <div>
            <span className={`inline-flex items-center gap-2 rounded-full ${data.tone} ${data.ink} px-3 py-1 text-[12.5px] font-medium`}>
              <Icon size={14} />
              {data.eyebrow}
            </span>
            <h1 className="mt-5 max-w-[620px] text-[40px] font-light leading-[1.05] tracking-[-1.2px] md:text-[56px]">
              {data.heroTitle}
            </h1>
            <p className="mt-5 max-w-[520px] text-[16px] leading-[1.6] text-[var(--color-gravel)] md:text-[17px]">
              {data.heroSub}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#cta" className="inline-flex h-11 cursor-pointer items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition hover:bg-neutral-800">
                Talk to sales
              </a>
              <Link to="/signup" className="inline-flex h-11 cursor-pointer items-center gap-1.5 rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]">
                Try on Playground
                <ArrowUpRight size={15} />
              </Link>
            </div>
          </div>

          {/* framed media */}
          <div className="overflow-hidden rounded-[20px] border border-[var(--color-chalk)] bg-white shadow-[0_40px_90px_-55px_rgba(0,0,0,0.5)]">
            {data.media.type === "video" ? (
              <video
                src={data.media.src}
                poster={data.media.poster}
                autoPlay
                muted
                loop
                playsInline
                className="aspect-[16/10] w-full object-cover"
              />
            ) : (
              <img src={data.media.src} alt={`${data.eyebrow} video intelligence`} loading="lazy" className="aspect-[16/10] w-full object-cover" />
            )}
          </div>
        </div>
      </Section>

      {/* ---------- numbered features ---------- */}
      <Section className="py-14">
        <div className="grid gap-px overflow-hidden rounded-[24px] border border-[var(--color-chalk)] bg-[var(--color-chalk)] md:grid-cols-3">
          {data.features.map((f) => (
            <div key={f.n} className="bg-white p-8">
              <span className={`text-[15px] font-mono ${data.ink}`}>{f.n}</span>
              <h3 className="mt-3 text-[20px] font-semibold leading-snug">{f.title}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-[var(--color-gravel)]">{f.body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ---------- use cases ---------- */}
      <Section className="py-14">
        <h2 className="max-w-[640px] text-[32px] font-light leading-[1.08] tracking-[-0.8px] md:text-[42px]">
          {data.useCasesHeading}
        </h2>
        <div className="mt-10 grid gap-8 md:grid-cols-3">
          {data.useCaseGroups.map((g) => (
            <div key={g.title}>
              <h3 className="text-[16px] font-semibold">{g.title}</h3>
              <ul className="mt-4 space-y-3">
                {g.items.map((item) => (
                  <li key={item} className="flex items-start gap-2.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">
                    <Check size={16} className={`mt-0.5 shrink-0 ${data.ink}`} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {/* ---------- value pillars ---------- */}
      <Section className="py-14">
        <div className={`rounded-[24px] ${data.tone} p-10`}>
          <h2 className="max-w-[640px] text-[30px] font-light tracking-[-0.6px] md:text-[38px]">
            State-of-the-art, straight out of the box.
          </h2>
          <p className="mt-3 max-w-[560px] text-[15px] leading-[1.6] text-[var(--color-obsidian)]/70">
            Use it on any cloud, fine-tune with your own data, and deploy your custom model. The keys
            to state-of-the-art video AI that adapts to your needs.
          </p>
          <div className="mt-8 grid gap-px overflow-hidden rounded-[18px] bg-black/5 sm:grid-cols-2 lg:grid-cols-4">
            {VALUE_PILLARS.map((p) => (
              <div key={p.title} className="bg-white/80 p-6">
                <h3 className="text-[16px] font-semibold">{p.title}</h3>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-[var(--color-gravel)]">{p.body}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ---------- code sample ---------- */}
      <Section className="py-14">
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div>
            <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">
              Integrate with your SDK, and your vision.
            </h2>
            <p className="mt-3 max-w-[460px] text-[15px] leading-relaxed text-[var(--color-gravel)]">
              Do more with your video from day one with easy APIs and developer-friendly SDKs. Ready
              to integrate and adapt.
            </p>
            <Link to="/build" className="mt-5 inline-flex items-center gap-1 text-[14px] font-medium text-[var(--color-accent-blue)] hover:gap-1.5">
              Get the SDK
              <ArrowUpRight size={15} />
            </Link>
          </div>
          <div className="overflow-hidden rounded-2xl border border-[var(--color-chalk)] bg-[#0f1115] shadow-[0_30px_70px_-40px_rgba(0,0,0,0.6)]">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
              <span className="text-[12px] text-white/50">example.py</span>
              <button onClick={copy} className="inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 text-[12px] text-white/70 transition hover:bg-white/10 hover:text-white">
                {copied ? <Check size={13} /> : <Copy size={13} />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="overflow-x-auto px-4 py-4 text-[12.5px] leading-relaxed text-[#e6e6e6]"><code>{SOLUTION_CODE}</code></pre>
          </div>
        </div>
      </Section>

      {/* ---------- pricing ---------- */}
      <Section className="py-14">
        <div className="text-center">
          <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">Play for free. Pay as you go.</h2>
          <p className="mx-auto mt-3 max-w-[520px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
            Start with a foundational model and pay only for what you use.
          </p>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {PRICING_TIERS.map((t) => (
            <div
              key={t.name}
              className={`flex flex-col rounded-[20px] border bg-white p-7 ${
                t.highlight ? "border-[var(--color-accent-blue)] shadow-[0_24px_60px_-40px_rgba(4,71,255,0.5)]" : "border-[var(--color-chalk)]"
              }`}
            >
              <p className="text-[18px] font-semibold">{t.name}</p>
              <p className="mt-1 text-[13px] text-[var(--color-gravel)]">{t.purpose}</p>
              <p className="mt-5 text-[13px] font-medium text-[var(--color-obsidian)]">Indexing</p>
              <p className="text-[13px] text-[var(--color-gravel)]">{t.indexing}</p>
              <Link
                to={t.to}
                className={`mt-6 inline-flex h-10 items-center justify-center rounded-full px-5 text-[13px] font-medium transition ${
                  t.highlight
                    ? "bg-[var(--color-obsidian)] text-white hover:bg-neutral-800"
                    : "border border-[var(--color-chalk)] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
                }`}
              >
                {t.cta}
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-6 text-center text-[13px]">
          <Link to="/pricing" className="font-medium text-[var(--color-accent-blue)] hover:underline">
            See full pricing
          </Link>
        </p>
      </Section>

      {/* ---------- final CTA ---------- */}
      <Section id="cta" className="pb-24 pt-8">
        <div className="rounded-[32px] bg-gradient-warm px-8 py-20 text-center md:py-24">
          <h2 className="mx-auto max-w-[720px] text-[34px] font-light leading-[1.05] tracking-[-1px] md:text-[48px]">
            {data.ctaTitle}
          </h2>
          <p className="mx-auto mt-5 max-w-[520px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
            Try your own video in the free Playground, or talk to our team.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link to="/signup" className="inline-flex h-11 items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition hover:bg-neutral-800">
              Try on Playground
              <ArrowUpRight size={16} />
            </Link>
            <Link to="/pricing" className="inline-flex h-11 items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]">
              Talk to sales
            </Link>
          </div>
        </div>
      </Section>

      <Footer />
    </main>
  );
}

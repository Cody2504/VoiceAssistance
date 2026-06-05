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
import { Footer } from "@/pages/landing/sections/Footer";

/**
 * Solutions page — mirrors twelvelabs.io/enterprise:
 * hero · industries · stats band · case studies · secure-by-design ·
 * partners · final CTA. Light theme, guest-facing, no backend.
 */

const INDUSTRIES = [
  { icon: Clapperboard, title: "Media & Entertainment", body: "Turn archives into assets — timestamped clips from every shoot in seconds, not days.", tone: "bg-[#fbdfff]", ink: "text-[#5e3b66]" },
  { icon: Megaphone, title: "Advertising", body: "Contextual ad placement driven by understanding, not metadata. Brand-safe scenes, no manual review.", tone: "bg-[#fde3a2]", ink: "text-[#7d5d0c]" },
  { icon: ShieldCheck, title: "Government & Security", body: "Evidence management, anomaly detection and after-incident reporting in minutes.", tone: "bg-[#c4eefe]", ink: "text-[#26586d]" },
  { icon: Car, title: "Automotive", body: "Scene understanding at scale for in-cabin, ADAS and fleet footage.", tone: "bg-[#d9f5dd]", ink: "text-[#2f6b3a]" },
  { icon: Landmark, title: "Public Sector", body: "Searchable, auditable video intelligence for agencies and smart cities.", tone: "bg-[#e7e3ff]", ink: "text-[#4a3b8c]" },
  { icon: Sparkles, title: "Creative Industries", body: "From liabilities to strategic assets — surface the best moments automatically.", tone: "bg-[#ffe1d6]", ink: "text-[#8a4326]" },
];

const STATS = [
  { value: "+13.1%", label: "Higher retrieval accuracy vs. prior baselines" },
  { value: "10×", label: "Faster content review and compliance scanning" },
  { value: "4 hrs", label: "Indexed and searchable from a single API call" },
];

const CASES = [
  { tag: "SPORTS", title: "Surface the best plays", body: "Package highlight reels by searching games for exact moments fans care about." },
  { tag: "BROADCAST", title: "Mine the archive", body: "What took a research team three days now takes three seconds." },
  { tag: "ADTECH", title: "Contextual targeting", body: "Place ads only in brand-safe scenes — no tags, no manual review." },
];

const SECURITY = [
  { icon: Lock, title: "Encrypted by default", body: "Data encrypted in transit and at rest across the pipeline." },
  { icon: Server, title: "Deploy where you want", body: "Shared, dedicated, or private — the stack runs in your environment." },
  { icon: KeyRound, title: "SSO / SAML & audit logs", body: "Enterprise access controls and full auditability." },
];

function Section({ id, children, className = "" }: { id?: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={`mx-auto max-w-[1200px] px-6 ${className}`}>
      {children}
    </section>
  );
}

export default function Solutions() {
  return (
    <main className="bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
      {/* hero */}
      <Section className="pt-20 pb-14 text-center md:pt-24">
        <p className="mb-5 text-[13px] uppercase tracking-[0.18em] text-[var(--color-gravel)]">
          Video AI for enterprises
        </p>
        <h1 className="mx-auto max-w-[900px] text-[44px] font-light leading-[1.05] tracking-[-1.2px] text-[var(--color-obsidian)] md:text-[60px]">
          Unlock the value of video intelligence.
        </h1>
        <p className="mx-auto mt-6 max-w-[640px] text-[16px] leading-[1.55] text-[var(--color-gravel)] md:text-[17px]">
          Video intelligence, fine-tuned to your industry — turning raw, passive footage into a
          strategic asset your teams can actually use.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <a href="/#cta" className="inline-flex h-11 cursor-pointer items-center rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]">
            Talk to sales
          </a>
          <Link to="/signup" className="inline-flex h-11 cursor-pointer items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]">
            Start free ↗
          </Link>
        </div>
      </Section>

      {/* industries */}
      <Section id="industries" className="py-16">
        <h2 className="text-center text-[30px] font-light tracking-[-0.6px] md:text-[38px]">
          Fine-tuned to your industry
        </h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {INDUSTRIES.map((it) => {
            const Icon = it.icon;
            return (
              <div key={it.title} className={`rounded-[20px] ${it.tone} p-6`}>
                <span className={`inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white/70 ${it.ink}`}>
                  <Icon size={20} />
                </span>
                <h3 className={`mt-4 text-[18px] font-semibold ${it.ink}`}>{it.title}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-obsidian)]/70">{it.body}</p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* stats band */}
      <Section className="py-16">
        <div className="grid gap-8 rounded-[24px] border border-[var(--color-chalk)] bg-white p-10 sm:grid-cols-3">
          {STATS.map((s) => (
            <div key={s.value} className="text-center">
              <div className="text-[44px] font-light tabular-nums tracking-[-1px] text-[var(--color-obsidian)]">{s.value}</div>
              <p className="mt-2 text-[13px] leading-snug text-[var(--color-gravel)]">{s.label}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* case studies */}
      <Section id="cases" className="py-16">
        <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">Real-world case studies</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {CASES.map((c) => (
            <div key={c.title} className="rounded-[20px] border border-[var(--color-chalk)] bg-white p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">{c.tag}</p>
              <h3 className="mt-2 text-[18px] font-semibold">{c.title}</h3>
              <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{c.body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* secure by design */}
      <Section id="security" className="py-16">
        <div className="rounded-[24px] bg-[var(--color-powder)] p-10">
          <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">Secure by design</h2>
          <p className="mt-2 max-w-[640px] text-[15px] text-[var(--color-gravel)]">
            Encrypted data handling and enterprise controls — the entire intelligence stack deploys where you want.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {SECURITY.map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.title} className="rounded-[18px] border border-[var(--color-chalk)] bg-white p-6">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
                    <Icon size={20} />
                  </span>
                  <h3 className="mt-4 text-[16px] font-semibold">{s.title}</h3>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{s.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      {/* final CTA */}
      <Section className="py-20 text-center">
        <h2 className="mx-auto max-w-[760px] text-[34px] font-light tracking-[-0.8px] md:text-[46px]">
          Start building with Jockey.
        </h2>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/signup" className="inline-flex h-11 cursor-pointer items-center rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]">
            Start free ↗
          </Link>
          <a href="/#cta" className="inline-flex h-11 cursor-pointer items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]">
            Talk to sales
          </a>
        </div>
      </Section>

      <Footer />
    </main>
  );
}

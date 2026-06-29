import { useState } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  TerminalSquare,
  Blocks,
  Users,
  Search,
  Sparkles,
  Layers,
  Boxes,
  MessagesSquare,
  LifeBuoy,
  Copy,
  Check,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Footer } from "@/pages/landing/sections/Footer";

/**
 * Build / Developer Hub — mirrors twelvelabs.io/developer-hub:
 * hero · quick links · "Try our API" · SDKs · Sample Apps ·
 * browse by product · models · support. Light theme, no backend.
 */

const CODE = `from jockey import Jockey

client = Jockey("<YOUR_API_KEY>")

# Create an index and upload a video
index = client.index.create(name="My First Index")
task = client.task.create(index_id=index.id, file="match.mp4")
task.wait_for_done()

# Search it in natural language
result = client.search.query(index.id, "the winning goal")
print(result)`;

function Section({ id, children, className = "" }: { id?: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={`mx-auto max-w-[1200px] px-6 ${className}`}>
      {children}
    </section>
  );
}

export default function Build() {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  function copy() {
    void navigator.clipboard?.writeText(CODE).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  }

  const QUICK_LINKS = [
    { icon: BookOpen, label: t("marketing.build.quick_links.api_ref_label"), desc: t("marketing.build.quick_links.api_ref_desc"), to: "/build#api" },
    { icon: TerminalSquare, label: t("marketing.build.quick_links.sdks_label"), desc: t("marketing.build.quick_links.sdks_desc"), to: "/build#sdks" },
    { icon: Blocks, label: t("marketing.build.quick_links.samples_label"), desc: t("marketing.build.quick_links.samples_desc"), to: "/build#samples" },
    { icon: Users, label: t("marketing.build.quick_links.community_label"), desc: t("marketing.build.quick_links.community_desc"), to: "/build#support" },
  ];

  const PRODUCTS = [
    { icon: Search, title: t("marketing.build.products.search_title"), body: t("marketing.build.products.search_body"), to: "/playground/search" },
    { icon: Sparkles, title: t("marketing.build.products.analyze_title"), body: t("marketing.build.products.analyze_body"), to: "/playground/analyze" },
    { icon: Layers, title: t("marketing.build.products.segment_title"), body: t("marketing.build.products.segment_body"), to: "/playground/segment" },
  ];

  const SAMPLES = [
    { lang: "PYTHON", title: t("marketing.build.samples.viral_title"), body: t("marketing.build.samples.viral_body") },
    { lang: "NODE", title: t("marketing.build.samples.social_title"), body: t("marketing.build.samples.social_body") },
    { lang: "PYTHON", title: t("marketing.build.samples.shade_title"), body: t("marketing.build.samples.shade_body") },
  ];

  const MODELS = [
    { name: "Sprint", kind: t("marketing.build.models.viclip_kind"), body: t("marketing.build.models.viclip_body") },
    { name: "Stride", kind: t("marketing.build.models.qwen_kind"), body: t("marketing.build.models.qwen_body") },
  ];

  const SUPPORT = [
    { icon: LifeBuoy, title: t("marketing.build.support.contact_title"), body: t("marketing.build.support.contact_body"), cta: t("marketing.build.support.contact_cta"), to: "/#cta" },
    { icon: MessagesSquare, title: t("marketing.build.support.community_title"), body: t("marketing.build.support.community_body"), cta: t("marketing.build.support.community_cta"), to: "/build#support" },
  ];

  return (
    <main className="bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
      {/* hero */}
      <Section className="pt-20 pb-12 text-center md:pt-24">
        <p className="mb-5 text-[13px] uppercase tracking-[0.18em] text-[var(--color-gravel)]">{t("marketing.build.hero_eyebrow")}</p>
        <h1 className="mx-auto max-w-[860px] text-[44px] font-light leading-[1.05] tracking-[-1.2px] md:text-[60px]">
          {t("marketing.build.hero_heading")}
        </h1>
        <p className="mx-auto mt-6 max-w-[620px] text-[16px] leading-[1.55] text-[var(--color-gravel)] md:text-[17px]">
          {t("marketing.build.hero_sub")}
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link to="/signup" className="inline-flex h-11 cursor-pointer items-center rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]">
            {t("marketing.build.go_to_playground")}
          </Link>
          <a href="#api" className="inline-flex h-11 cursor-pointer items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]">
            {t("actions.read_docs")}
          </a>
        </div>
      </Section>

      {/* quick links */}
      <Section className="pb-8">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_LINKS.map((q) => {
            const Icon = q.icon;
            return (
              <Link key={q.label} to={q.to} className="group flex items-center gap-3 rounded-2xl border border-[var(--color-chalk)] bg-white px-4 py-4 transition hover:border-[var(--color-accent-blue)]">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--color-chalk)] bg-[var(--color-eggshell)] text-[var(--color-obsidian)] transition group-hover:text-[var(--color-accent-blue)]">
                  <Icon size={17} />
                </span>
                <span>
                  <span className="block text-[14px] font-medium">{q.label}</span>
                  <span className="block text-[12px] text-[var(--color-gravel)]">{q.desc}</span>
                </span>
              </Link>
            );
          })}
        </div>
      </Section>

      {/* try our API */}
      <Section id="api" className="py-12">
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div>
            <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.build.try_api_heading")}</h2>
            <p className="mt-3 max-w-[460px] text-[15px] leading-relaxed text-[var(--color-gravel)]">
              {t("marketing.build.try_api_body")}
            </p>
            <a href="#sdks" className="mt-5 inline-flex items-center gap-1 text-[14px] font-medium text-[var(--color-accent-blue)] hover:gap-1.5">
              {t("marketing.build.get_sdk")}
            </a>
          </div>
          <div className="overflow-hidden rounded-2xl border border-[var(--color-chalk)] bg-[#0f1115] shadow-[0_30px_70px_-40px_rgba(0,0,0,0.6)]">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
              <span className="text-[12px] text-white/50">example.py</span>
              <button onClick={copy} className="inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 text-[12px] text-white/70 transition hover:bg-white/10 hover:text-white">
                {copied ? <Check size={13} /> : <Copy size={13} />}
                {copied ? t("actions.copied") : t("actions.copy")}
              </button>
            </div>
            <pre className="overflow-x-auto px-4 py-4 text-[12.5px] leading-relaxed text-[#e6e6e6]"><code>{CODE}</code></pre>
          </div>
        </div>
      </Section>

      {/* SDKs */}
      <Section id="sdks" className="py-12">
        <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.build.sdks_heading")}</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {["Python", "Node"].map((sdk) => (
            <div key={sdk} className="flex items-center justify-between rounded-2xl border border-[var(--color-chalk)] bg-white px-6 py-5">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--color-chalk)] bg-[var(--color-eggshell)]">
                  <TerminalSquare size={18} />
                </span>
                <div>
                  <p className="text-[15px] font-semibold">{sdk} SDK</p>
                  <p className="text-[12px] text-[var(--color-gravel)]">{t("marketing.build.sdk_official")}</p>
                </div>
              </div>
              <span className="rounded-md bg-[var(--color-powder)] px-2.5 py-1 font-mono text-[12px] text-[var(--color-gravel)]">
                {sdk === "Python" ? "pip install jockey" : "npm i jockey"}
              </span>
            </div>
          ))}
        </div>
      </Section>

      {/* sample apps */}
      <Section id="samples" className="py-12">
        <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.build.samples_heading")}</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {SAMPLES.map((s) => (
            <div key={s.title} className="rounded-[20px] border border-[var(--color-chalk)] bg-white p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">{s.lang}</p>
              <h3 className="mt-2 text-[17px] font-semibold">{s.title}</h3>
              <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{s.body}</p>
              <div className="mt-4 flex gap-3 text-[13px] font-medium">
                <span className="text-[var(--color-accent-blue)]">{t("marketing.build.sample_tutorial")}</span>
                <span className="text-[var(--color-gravel)]">{t("marketing.build.sample_code")}</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* browse by product */}
      <Section className="py-12">
        <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.build.products_heading")}</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {PRODUCTS.map((p) => {
            const Icon = p.icon;
            return (
              <Link key={p.title} to={p.to} className="group rounded-[20px] border border-[var(--color-chalk)] bg-white p-6 transition hover:border-[var(--color-accent-blue)]">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)] transition group-hover:text-[var(--color-accent-blue)]">
                  <Icon size={20} />
                </span>
                <h3 className="mt-4 text-[18px] font-semibold">{p.title}</h3>
                <p className="mt-1.5 text-[14px] text-[var(--color-gravel)]">{p.body}</p>
              </Link>
            );
          })}
        </div>
      </Section>

      {/* models */}
      <Section className="py-12">
        <div className="rounded-[24px] bg-[var(--color-powder)] p-10">
          <div className="flex items-center gap-2">
            <Boxes size={20} />
            <h2 className="text-[26px] font-light tracking-[-0.5px] md:text-[32px]">{t("marketing.build.models_heading")}</h2>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {MODELS.map((m) => (
              <div key={m.name} className="rounded-[18px] border border-[var(--color-chalk)] bg-white p-6">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">{m.kind}</p>
                <h3 className="mt-2 text-[18px] font-semibold">{m.name}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-gravel)]">{m.body}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* support */}
      <Section id="support" className="py-12 pb-20">
        <h2 className="text-[30px] font-light tracking-[-0.6px] md:text-[38px]">{t("marketing.build.support_heading")}</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {SUPPORT.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.title} className="flex items-start gap-4 rounded-[20px] border border-[var(--color-chalk)] bg-white p-6">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)]">
                  <Icon size={20} />
                </span>
                <div>
                  <h3 className="text-[17px] font-semibold">{s.title}</h3>
                  <p className="mt-1 text-[14px] text-[var(--color-gravel)]">{s.body}</p>
                  <a href={s.to} className="mt-3 inline-flex text-[13px] font-medium text-[var(--color-accent-blue)] hover:underline">{s.cta} →</a>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      <Footer />
    </main>
  );
}

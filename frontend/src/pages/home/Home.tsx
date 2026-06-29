import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Footer } from "@/pages/landing/sections/Footer";

/**
 * Marketing homepage, a faithful (static) reconstruction of the twelvelabs.io
 * homepage composition on the Jockey light skin:
 *   hero · dark "Results in minutes" infrastructure band · capabilities shell ·
 *   metrics + trusted-by · industry cards · secure-by-design · models · CTA.
 *
 * Signature TwelveLabs device: hairline-bordered grid (1px chalk side borders,
 * cells split by borders), split headers (big heading left / subtitle right),
 * ghost "Learn more" pills with an arrow. Headings use the Inter display scale
 * (Waldenburg-like sans), not the ElevenLabs serif. No JS interactions.
 */

// Deterministic isometric "data cylinder" for the Results-in-minutes diagram:
// a tilted grid cylinder (longitude rulings + latitude rings) with a scatter of
// indexed-moment particles. Computed once at module load; no randomness at runtime.
const DEG = Math.PI / 180;
function buildInfraDiagram() {
  const F = { x: 250, y: 360 };
  const axis = { x: 300, y: -120 };
  const rx0 = 80, ry0 = 168, phi = -18 * DEG;
  const cos = Math.cos(phi), sin = Math.sin(phi);
  const scaleAt = (t: number) => 1 - 0.36 * t;
  const pt = (t: number, theta: number, radFrac = 1) => {
    const s = scaleAt(t) * radFrac;
    const lx = rx0 * s * Math.cos(theta);
    const ly = ry0 * s * Math.sin(theta);
    return { x: F.x + axis.x * t + (lx * cos - ly * sin), y: F.y + axis.y * t + (lx * sin + ly * cos) };
  };
  const longs: string[] = [];
  for (let i = 0; i < 16; i++) {
    const th = (i / 16) * 2 * Math.PI;
    const a = pt(0, th), b = pt(1, th);
    longs.push(`${a.x.toFixed(1)},${a.y.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`);
  }
  const lats: string[] = [];
  for (const t of [0, 0.34, 0.68, 1]) {
    const pts: string[] = [];
    for (let i = 0; i <= 48; i++) {
      const p = pt(t, (i / 48) * 2 * Math.PI);
      pts.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
    }
    lats.push(pts.join(" "));
  }
  const palette = ["#eef6a6", "#d4ec7c", "#a9d36a", "#7fb85a", "#5d7a40"];
  const dots: { x: number; y: number; c: string; sz: number }[] = [];
  let seed = 7;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  for (let i = 0; i < 70; i++) {
    const p = pt(rnd() * 0.5, rnd() * 2 * Math.PI, 0.12 + rnd() * 0.88);
    dots.push({ x: p.x, y: p.y, c: palette[Math.floor(rnd() * palette.length)], sz: 6 + rnd() * 5 });
  }
  return { longs, lats, dots };
}
const INFRA_DIAGRAM = buildInfraDiagram();

const BUILT_ON = [
  { slug: "pytorch", name: "PyTorch" },
  { slug: "huggingface", name: "Hugging Face" },
  { slug: "fastapi", name: "FastAPI" },
  { slug: "redis", name: "Redis" },
  { slug: "minio", name: "MinIO" },
  { slug: "docker", name: "Docker" },
];

// Industry carousel. CARDS render in display order [Public, Creative, AdTech];
// PILL_ORDER lists the pills in reference order, each centering its card index.
// Cards are full-bleed (escape the max-width container) and link to solutions.
const PILL_ORDER = [1, 2, 0]; // Creative, Advertising, Public Sector

const FILLED =
  "inline-flex h-11 items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition hover:bg-neutral-800 active:scale-[0.98]";
const GHOST_LIGHT =
  "inline-flex h-11 items-center gap-1.5 rounded-[18px] border border-[var(--color-obsidian)] px-5 text-[14px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)] active:scale-[0.98]";
const GHOST_DARK =
  "inline-flex h-11 items-center gap-1.5 rounded-[18px] border border-white/70 px-5 text-[14px] font-medium text-[#f4f3f3] transition hover:bg-white/10 active:scale-[0.98]";

function Container({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1200px] px-6 ${className}`}>{children}</div>;
}

export default function Home() {
  return (
    <main className="bg-[#f4f3f3] text-[var(--color-obsidian)]">
      <Hero />
      <ResultsBand />
      <Capabilities />
      <Metrics />
      <Industries />
      <Secure />
      <Models />
      <FinalCta />
      <Footer />
    </main>
  );
}

/* ---------------- hero ---------------- */
function Hero() {
  const { t } = useTranslation();
  return (
    <Container className="pt-20 pb-16 text-center md:pt-24">
      <h1 className="fade-rise mx-auto max-w-[960px] text-[44px] font-medium leading-[1.02] tracking-[-1.5px] text-[var(--color-obsidian)] sm:text-[60px] lg:text-[72px]">
        {t("marketing.home.hero_heading")}
      </h1>
      <p className="fade-rise-delayed mx-auto mt-6 max-w-[620px] text-[16px] leading-[1.6] text-[var(--color-gravel)] md:text-[18px]">
        {t("marketing.home.hero_sub")}
      </p>
      <div className="fade-rise-delayed mt-9 flex flex-wrap items-center justify-center gap-3">
        <Link to="/signup" className={FILLED}>
          {t("marketing.home.try_playground")}
          <ArrowUpRight size={16} />
        </Link>
        <a href="#cta" className={GHOST_LIGHT}>
          {t("marketing.home.talk_to_sales")}
        </a>
      </div>

      <div className="fade-rise-delayed mx-auto mt-14 max-w-[1000px] overflow-hidden rounded-[20px] border border-[var(--color-chalk)] bg-white shadow-card">
        <video
          src="/twelvelabs/search-bg.mp4"
          poster="/twelvelabs/search-bg.jpg"
          autoPlay
          muted
          loop
          playsInline
          className="aspect-[16/9] w-full object-cover"
        />
      </div>
    </Container>
  );
}

/* ---------------- dark "Results in minutes" infrastructure band ---------------- */
function ResultsBand() {
  const { t } = useTranslation();
  return (
    <section className="mt-20 bg-[#1d1c1b] text-[#f4f3f3]">
      <Container className="border-x border-white/12 py-0">
        {/* header row */}
        <div className="grid border-b border-white/12 md:grid-cols-2">
          <div className="border-white/12 py-12 pr-8 md:border-r">
            <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
              {t("marketing.home.results_heading")}
            </h2>
          </div>
          <div className="flex flex-col items-start gap-6 py-12 md:pl-10">
            <p className="max-w-[420px] text-[15px] leading-[1.6] text-white/70">
              {t("marketing.home.results_sub")}
            </p>
            <Link to="/build" className={GHOST_DARK}>
              {t("marketing.home.developer_hub")}
              <ArrowUpRight size={15} />
            </Link>
          </div>
        </div>

        {/* content row: numbered list + diagram */}
        <div className="grid md:grid-cols-2">
          <div className="border-white/12 py-14 pr-8 md:border-r">
            <div className="flex w-[290px] max-w-full items-center rounded-[13px] bg-[#333231] px-4 py-2.5 text-[18px] font-medium text-white">
              {t("marketing.home.infra_step1")}
            </div>
            <div className="mt-5 max-w-[420px]">
              <p className="text-[14px] leading-[1.6] text-white/70">
                {t("marketing.home.infra_body")}
              </p>
              <Link
                to="/build"
                className="mt-5 inline-flex items-center gap-1.5 rounded-[14px] border border-white/70 px-3.5 py-1.5 text-[13px] font-medium text-[#f4f3f3] transition hover:bg-white/10"
              >
                {t("actions.learn_more")}
                <ArrowUpRight size={14} />
              </Link>
            </div>
            <div className="mt-12 space-y-7 text-[18px] font-medium text-white/55">
              <div>{t("marketing.home.infra_step2")}</div>
              <div>{t("marketing.home.infra_step3")}</div>
              <div>{t("marketing.home.infra_step4")}</div>
            </div>
          </div>
          <div className="flex items-center py-10 md:pl-10">
            <InfraDiagram />
          </div>
        </div>
      </Container>
    </section>
  );
}

function InfraDiagram() {
  const { t } = useTranslation();
  const { longs, lats, dots } = INFRA_DIAGRAM;
  return (
    <div className="relative aspect-[5/4] w-full overflow-hidden rounded-[28px] border border-white/10 bg-[#211f1e]">
      <svg viewBox="0 0 760 620" preserveAspectRatio="xMidYMid meet" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <g fill="none" stroke="rgba(255,255,255,0.16)" strokeWidth="1">
          {lats.map((p, i) => <polyline key={`lat${i}`} points={p} />)}
          {longs.map((p, i) => <polyline key={`lon${i}`} points={p} />)}
        </g>
        {dots.map((d, i) => (
          <rect
            key={i}
            x={(d.x - d.sz / 2).toFixed(1)}
            y={(d.y - d.sz / 2).toFixed(1)}
            width={d.sz.toFixed(1)}
            height={d.sz.toFixed(1)}
            rx="1.5"
            fill={d.c}
            opacity="0.92"
            transform={`rotate(45 ${d.x.toFixed(1)} ${d.y.toFixed(1)})`}
          />
        ))}
      </svg>
      <Callout className="left-[34%] top-[7%]" label={t("marketing.home.speed_label")} lines={t("marketing.home.speed_lines").split("\n")} />
      <Callout className="bottom-[7%] left-[7%]" label={t("marketing.home.scale_label")} lines={t("marketing.home.scale_lines").split("\n")} />
      <Callout className="bottom-[7%] right-[6%]" label={t("marketing.home.proprietary_label")} lines={t("marketing.home.proprietary_lines").split("\n")} />
    </div>
  );
}

function Callout({ className, label, lines }: { className: string; label: string; lines: string[] }) {
  return (
    <div className={`absolute max-w-[210px] ${className}`}>
      <span className="inline-flex rounded-[7px] border border-white/35 px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-white/90">
        {label}
      </span>
      <p className="mt-2 text-[12px] leading-[1.45] text-white/55">
        {lines.map((l, i) => <span key={i} className="block">{l}</span>)}
      </p>
    </div>
  );
}

/* ---------------- capabilities (frosted shell, auto-rotating list) ---------------- */
const CAP_ROTATE_MS = 4500;
function Capabilities() {
  const { t } = useTranslation();
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  const CAPS = [
    { title: t("marketing.home.caps.search_title"), body: t("marketing.home.caps.search_body"), v: "tl_01" },
    { title: t("marketing.home.caps.segment_title"), body: t("marketing.home.caps.segment_body"), v: "tl_02" },
    { title: t("marketing.home.caps.compliance_title"), body: t("marketing.home.caps.compliance_body"), v: "tl_03" },
    { title: t("marketing.home.caps.highlights_title"), body: t("marketing.home.caps.highlights_body"), v: "tl_04" },
    { title: t("marketing.home.caps.insights_title"), body: t("marketing.home.caps.insights_body"), v: "tl_05" },
  ];

  // Auto-advance like the real site; pause on hover and skip entirely for
  // reduced-motion users. Re-arms on every `active` change, so a manual click
  // grants a full interval before the next auto-step.
  useEffect(() => {
    if (paused) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setActive((a) => (a + 1) % CAPS.length), CAP_ROTATE_MS);
    return () => window.clearInterval(id);
  }, [paused, active]);

  // All clips stay mounted (remounting a <video> reloads it → a flash). Only the
  // active clip plays; the rest are paused to save decode cost.
  const vidRefs = useRef<(HTMLVideoElement | null)[]>([]);
  useEffect(() => {
    vidRefs.current.forEach((v, i) => {
      if (!v) return;
      if (i === active) void v.play().catch(() => {});
      else v.pause();
    });
  }, [active]);
  return (
    <section className="relative overflow-hidden">
      {/* full-bleed pastel wash so the frosted shell actually reads as frosted */}
      <img
        src="/twelvelabs/cap-bg.svg"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full object-cover object-top"
      />
      <Container className="relative py-20">
        {/* bordered split header */}
      <div className="grid border-x border-[var(--color-chalk)] md:grid-cols-2">
        <div className="py-10 pr-8 md:border-r md:border-[var(--color-chalk)]">
          <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
            {t("marketing.home.caps_heading")}
          </h2>
        </div>
        <div className="flex items-end py-10 md:pl-10">
          <p className="max-w-[440px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
            {t("marketing.home.caps_sub")}
          </p>
        </div>
      </div>

      {/* frosted interactive shell */}
      <div
        className="mt-12 overflow-hidden rounded-[48px] border border-[var(--color-chalk)] bg-white/55 shadow-card backdrop-blur"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <div className="grid items-center md:grid-cols-[0.82fr_1.18fr]">
          <div className="p-8 md:p-12">
            {CAPS.map((c, i) => {
              const on = i === active;
              return (
                <button
                  key={c.v}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setActive(i)}
                  className="block w-full cursor-pointer border-0 bg-transparent py-3.5 text-left"
                >
                  <h3
                    className={
                      "text-[22px] font-medium tracking-[-0.3px] transition-colors duration-300 ease-out " +
                      (on ? "text-[var(--color-obsidian)]" : "text-[var(--color-obsidian)]/45 hover:text-[var(--color-obsidian)]/70")
                    }
                  >
                    {c.title}
                  </h3>
                  {/* grid-rows 0fr→1fr expands the active item's body + progress smoothly */}
                  <div
                    className={
                      "grid transition-[grid-template-rows,opacity] duration-300 ease-out " +
                      (on ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0")
                    }
                  >
                    <div className="overflow-hidden">
                      <p className="pt-3 max-w-[430px] text-[14px] leading-[1.6] text-[var(--color-gravel)]">{c.body}</p>
                      {on && (
                        <div className="mt-4 h-px w-full overflow-hidden bg-[var(--color-chalk)]">
                          <div
                            className="h-full w-full origin-left bg-[var(--color-obsidian)]"
                            style={{
                              animation: `cap-progress ${CAP_ROTATE_MS}ms linear forwards`,
                              animationPlayState: paused ? "paused" : "running",
                            }}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <div className="flex items-center justify-center p-6 md:py-10 md:pr-10">
            <div className="relative w-full max-w-[600px]">
              {CAPS.map((c, i) => (
                <video
                  key={c.v}
                  ref={(el) => {
                    vidRefs.current[i] = el;
                  }}
                  src={`/twelvelabs/${c.v}.webm`}
                  muted
                  loop
                  playsInline
                  preload="auto"
                  aria-hidden={i !== active}
                  className={
                    "w-full object-contain transition-opacity duration-300 ease-out " +
                    (i === active ? "relative opacity-100" : "absolute inset-0 h-full opacity-0")
                  }
                />
              ))}
            </div>
          </div>
        </div>
      </div>
      </Container>
    </section>
  );
}

// Per-character color wave: a 2-char band of brand hues sweeps across each stat
// number and loops, matching the twelvelabs.io stat band. Runs only while in
// view; reduced-motion users see solid ink (no wave). Chars are aria-hidden and
// the full value is exposed via aria-label so screen readers read it normally.
const WAVE_HUES = ["#7a4dff", "#ff8caa", "#2563eb", "#87e3a5", "#ffd060"];

function ColorWaveNumber({ text, className }: { text: string; className?: string }) {
  const chars = [...text];
  const ref = useRef<HTMLDivElement>(null);
  const [head, setHead] = useState(-3);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !timer) {
          timer = setInterval(() => setHead((h) => (h > chars.length + 3 ? -3 : h + 1)), 220);
        } else if (!entry.isIntersecting && timer) {
          clearInterval(timer);
          timer = undefined;
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      if (timer) clearInterval(timer);
    };
  }, [chars.length]);

  return (
    <div ref={ref} className={className} aria-label={text}>
      {chars.map((ch, i) => {
        const lit = head - i >= 0 && head - i < 2;
        return (
          <span
            key={i}
            aria-hidden="true"
            style={{ color: lit ? WAVE_HUES[i % WAVE_HUES.length] : undefined, transition: "color 200ms ease" }}
          >
            {ch === " " ? " " : ch}
          </span>
        );
      })}
    </div>
  );
}

/* ---------------- metrics + trusted by ---------------- */
function Metrics() {
  const { t } = useTranslation();

  const METRICS = [
    { value: t("marketing.home.metrics.accuracy_value"), label: t("marketing.home.metrics.accuracy_label") },
    { value: t("marketing.home.metrics.speed_value"), label: t("marketing.home.metrics.speed_label") },
    { value: t("marketing.home.metrics.hours_value"), label: t("marketing.home.metrics.hours_label") },
  ];

  return (
    <Container className="py-20">
      <div className="grid gap-8 md:grid-cols-2">
        <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
          {t("marketing.home.metrics_heading")}
        </h2>
        <p className="max-w-[440px] self-end text-[15px] leading-[1.6] text-[var(--color-gravel)]">
          {t("marketing.home.metrics_sub")}
        </p>
      </div>

      <div className="mt-14 flex flex-col gap-10 sm:flex-row sm:gap-0">
        {METRICS.map((m, i) => (
          <div
            key={m.value}
            className={
              "flex-1 sm:px-10 sm:first:pl-0 sm:last:pr-0 " +
              (i > 0 ? "sm:border-l sm:border-[var(--color-chalk)]" : "")
            }
          >
            <ColorWaveNumber
              text={m.value}
              className="text-[48px] font-medium leading-none tracking-[-1.5px] tabular-nums text-[var(--color-obsidian)]"
            />
            <p className="mt-12 max-w-[260px] text-[14px] leading-[1.5] text-[var(--color-gravel)]">{m.label}</p>
          </div>
        ))}
      </div>

      <div className="mt-16">
        <p className="text-center text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-slate)]">
          {t("marketing.home.built_on")}
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-12 gap-y-8">
          {BUILT_ON.map((b) => (
            <img
              key={b.slug}
              src={`https://cdn.simpleicons.org/${b.slug}/b1b0b0`}
              alt={b.name}
              loading="lazy"
              className="h-7 w-auto"
            />
          ))}
        </div>
      </div>
    </Container>
  );
}

/* ---------------- industry cards (pill-switched centered carousel) ---------------- */
function Industries() {
  const { t } = useTranslation();
  const [active, setActive] = useState(1);
  const trackRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const [tx, setTx] = useState(0);

  const CARDS = [
    { pill: t("marketing.home.industries.public_pill"), title: t("marketing.home.industries.public_title"), body: t("marketing.home.industries.public_body"), to: "/solutions/government-and-security", img: "/twelvelabs/ind-public.png" },
    { pill: t("marketing.home.industries.creative_pill"), title: t("marketing.home.industries.creative_title"), body: t("marketing.home.industries.creative_body"), to: "/solutions/media-and-entertainment", img: "/twelvelabs/ind-creative.png" },
    { pill: t("marketing.home.industries.adtech_pill"), title: t("marketing.home.industries.adtech_title"), body: t("marketing.home.industries.adtech_body"), to: "/solutions/advertising", img: "/twelvelabs/ind-adtech.png" },
  ];

  useEffect(() => {
    const recalc = () => {
      const track = trackRef.current;
      const card = cardRefs.current[active];
      const viewport = track?.parentElement;
      if (!track || !card || !viewport) return;
      setTx(viewport.clientWidth / 2 - (card.offsetLeft + card.offsetWidth / 2));
    };
    recalc();
    window.addEventListener("resize", recalc);
    return () => window.removeEventListener("resize", recalc);
  }, [active]);

  return (
    <>
      <Container className="pt-20">
        {/* bordered split header */}
        <div className="grid border-x border-[var(--color-chalk)] md:grid-cols-2">
          <div className="py-10 pr-8 md:border-r md:border-[var(--color-chalk)]">
            <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
              {t("marketing.home.industries_heading")}
            </h2>
          </div>
          <div className="flex items-end py-10 md:pl-10">
            <p className="max-w-[440px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
              {t("marketing.home.industries_sub")}
            </p>
          </div>
        </div>

        {/* pills (reference order) */}
        <div className="mt-12 flex flex-wrap justify-center gap-2">
          {PILL_ORDER.map((idx) => (
            <button
              key={idx}
              type="button"
              aria-pressed={idx === active}
              onClick={() => setActive(idx)}
              className={
                "cursor-pointer rounded-[13px] px-4 py-2 text-[15px] font-medium transition " +
                (idx === active
                  ? "bg-[var(--color-obsidian)] text-white"
                  : "text-[var(--color-obsidian)]/45 hover:text-[var(--color-obsidian)]/80")
              }
            >
              {CARDS[idx].pill}
            </button>
          ))}
        </div>
      </Container>

      {/* full-bleed centered carousel (no max-width container) */}
      <div className="relative w-full overflow-hidden pb-20 pt-10">
        <div
          ref={trackRef}
          className="flex gap-6 transition-transform duration-[600ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
          style={{ transform: `translateX(${tx}px)` }}
        >
          {CARDS.map((it, i) => (
            <Link
              key={it.title}
              ref={(el) => { cardRefs.current[i] = el; }}
              to={it.to}
              aria-hidden={i !== active}
              tabIndex={i === active ? 0 : -1}
              className={
                "group relative aspect-[2/1] w-[84vw] max-w-[1040px] shrink-0 overflow-hidden rounded-[48px] transition-opacity duration-500 md:w-[68vw] " +
                (i === active ? "opacity-100" : "opacity-55 hover:opacity-80")
              }
            >
              <img src={it.img} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-r from-black/75 via-black/35 to-transparent" />
              <div className="absolute inset-0 flex flex-col justify-center p-10 md:p-14">
                <h3 className="text-[26px] font-medium tracking-[-0.5px] text-white md:text-[38px]">{it.title}</h3>
                <p className="mt-3 max-w-[420px] text-[14px] leading-[1.55] text-white/85 md:text-[15px]">{it.body}</p>
                <span className="mt-6 inline-flex w-fit items-center gap-1.5 rounded-[14px] border border-white/70 px-4 py-2 text-[13px] font-medium text-white transition group-hover:bg-white/10">
                  {t("actions.learn_more")}
                  <ArrowUpRight size={14} className="transition group-hover:translate-x-0.5" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

/* ---------------- secure by design (full-bleed pastel wash) ---------------- */
function Secure() {
  const { t } = useTranslation();
  return (
    <section className="relative overflow-hidden">
      <img
        src="/twelvelabs/secure-bg.svg"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full object-cover object-bottom"
      />
      <Container className="relative py-24">
        <div className="grid items-center gap-10 md:grid-cols-2">
          <div className="hidden justify-center md:flex">
            <img
              src="/twelvelabs/secure-art.png"
              alt={t("marketing.home.secure_img_alt")}
              loading="lazy"
              className="w-full max-w-[560px] object-contain"
            />
          </div>
          <div className="md:border-l md:border-[var(--color-obsidian)]/15 md:pl-12">
            <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">{t("marketing.home.secure_heading")}</h2>
            <p className="mt-5 max-w-[420px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
              {t("marketing.home.secure_body")}
            </p>
            <Link to="/solutions#security" className={`mt-7 ${GHOST_LIGHT}`}>
              {t("actions.learn_more")}
              <ArrowUpRight size={15} />
            </Link>
          </div>
        </div>
      </Container>
    </section>
  );
}

/* ---------------- models ---------------- */
function Models() {
  const { t } = useTranslation();

  const MODELS = [
    { kind: t("marketing.home.models.marengo_kind"), name: t("marketing.home.models.marengo_name"), body: t("marketing.home.models.marengo_body") },
    { kind: t("marketing.home.models.pegasus_kind"), name: t("marketing.home.models.pegasus_name"), body: t("marketing.home.models.pegasus_body") },
  ];

  return (
    <Container className="py-20">
      <h2 className="max-w-[640px] text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
        {t("marketing.home.models_heading")}
      </h2>
      <div className="mt-10 grid gap-5 md:grid-cols-2">
        {MODELS.map((m) => (
          <div key={m.name} className="rounded-[24px] border border-[var(--color-chalk)] bg-white p-8">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">{m.kind}</p>
            <h3 className="mt-3 text-[24px] font-medium tracking-[-0.4px]">{m.name}</h3>
            <p className="mt-4 text-[14px] leading-[1.6] text-[var(--color-gravel)]">{m.body}</p>
            <Link to="/product/product-overview" className="mt-5 inline-flex items-center gap-1 text-[14px] font-medium text-[var(--color-accent-blue)] hover:gap-1.5">
              {t("actions.learn_more")}
              <ArrowRight size={15} />
            </Link>
          </div>
        ))}
      </div>
    </Container>
  );
}

/* ---------------- final CTA ---------------- */
function FinalCta() {
  const { t } = useTranslation();
  return (
    <Container className="pb-24 pt-8">
      <div id="cta" className="rounded-[32px] bg-gradient-warm px-8 py-20 text-center md:py-24">
        <h2 className="mx-auto max-w-[760px] text-[36px] font-medium leading-[1.05] tracking-[-1px] text-[var(--color-obsidian)] md:text-[52px]">
          {t("marketing.home.cta_heading")}
        </h2>
        <p className="mx-auto mt-5 max-w-[520px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          {t("marketing.home.cta_sub")}
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link to="/signup" className={FILLED}>
            {t("marketing.home.start_building")}
            <ArrowUpRight size={16} />
          </Link>
          <Link to="/pricing" className={GHOST_LIGHT}>
            {t("nav.talk_to_sales")}
          </Link>
        </div>
      </div>
    </Container>
  );
}

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, ArrowRight } from "lucide-react";
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

// Each capability swaps the body copy and the matching TwelveLabs demo video
// (tl_01..tl_05, alpha .mov for Safari + .webm fallback, served from /public).
const CAPS = [
  { title: "Search & discover", body: "Search entire libraries in natural language. Locate actions, scenes, dialogue and on-screen objects across hours or years of footage, no tags needed.", v: "tl_01" },
  { title: "Segment content", body: "Automatically identify natural breaks, scene changes and pacing shifts in long-form video, grounded in what actually happened. Not a transcript reader, a video reasoner.", v: "tl_02" },
  { title: "Ensure compliance", body: "Detect unsafe, off-brand or non-compliant moments across the whole library in real time, with time-stamped, confidence-scored results.", v: "tl_03" },
  { title: "Create highlights", body: "Turn millions of clips into instant reels and trailers, pulling the moments that matter without a manual edit pass.", v: "tl_04" },
  { title: "Generate insights", body: "Analyze video at scale to surface patterns and signals, so teams can quickly see what is working and make better creative and editorial decisions.", v: "tl_05" },
];

const METRICS = [
  { value: "+13.1%", label: "Higher retrieval accuracy over prior baselines on internal benchmarks" },
  { value: "10x", label: "Faster content review and compliance scanning" },
  { value: "4 hrs", label: "Of footage indexed and searchable from a single API call" },
];

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
const CARDS = [
  { pill: "Public Sector", title: "Public Sector", body: "Evidence management, anomaly detection and after-incident reporting, all done in minutes using Jockey video intelligence.", to: "/solutions/government-and-security", img: "/twelvelabs/ind-public.png" },
  { pill: "Creative Industries", title: "Creative Industries", body: "Turn archives from liabilities to strategic assets. Within seconds: timestamped clips, from every year, every shoot. What used to take a research team three days takes three seconds.", to: "/solutions/media-and-entertainment", img: "/twelvelabs/ind-creative.png" },
  { pill: "Advertising and Marketing", title: "AdTech and Marketing", body: "Actually contextual targeting, driven by understanding, not metadata. Place ads only in brand-safe scenes, no tags, no manual review.", to: "/solutions/advertising", img: "/twelvelabs/ind-adtech.png" },
];
const PILL_ORDER = [1, 2, 0]; // Creative, Advertising, Public Sector

const MODELS = [
  { kind: "MULTIMODAL RETRIEVAL ENCODER", name: "Marengo-class retrieval", open: "ViCLIP", body: "Turns video into spatiotemporal embeddings, so every moment is findable by what is actually in it across speech, sound and visuals." },
  { kind: "VIDEO LANGUAGE MODEL", name: "Pegasus-class reasoning", open: "Qwen3-VL", body: "Reasons over the full temporal arc of an asset, tracking entities, causation and narrative rather than sampling a few frames." },
];

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
    <main className="bg-[var(--color-eggshell)] text-[var(--color-obsidian)]">
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
  return (
    <Container className="pt-20 pb-16 text-center md:pt-24">
      <h1 className="fade-rise mx-auto max-w-[960px] text-[44px] font-medium leading-[1.02] tracking-[-1.5px] text-[var(--color-obsidian)] sm:text-[60px] lg:text-[72px]">
        See the unseen. Know the unknowable.
      </h1>
      <p className="fade-rise-delayed mx-auto mt-6 max-w-[620px] text-[16px] leading-[1.6] text-[var(--color-gravel)] md:text-[18px]">
        Your video holds every insight, event and decision that mattered. Jockey turns raw footage
        into searchable, answerable, AI-ready data at scale.
      </p>
      <div className="fade-rise-delayed mt-9 flex flex-wrap items-center justify-center gap-3">
        <Link to="/signup" className={FILLED}>
          Try on Playground
          <ArrowUpRight size={16} />
        </Link>
        <a href="#cta" className={GHOST_LIGHT}>
          Talk to sales
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
  return (
    <section className="mt-20 bg-[#1d1c1b] text-[#f4f3f3]">
      <Container className="border-x border-white/12 py-0">
        {/* header row */}
        <div className="grid border-b border-white/12 md:grid-cols-2">
          <div className="border-white/12 py-12 pr-8 md:border-r">
            <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
              Results in minutes.
            </h2>
          </div>
          <div className="flex flex-col items-start gap-6 py-12 md:pl-10">
            <p className="max-w-[420px] text-[15px] leading-[1.6] text-white/70">
              Infrastructure for video intelligence, turning raw video into searchable, AI-ready
              data at massive scale.
            </p>
            <Link to="/build" className={GHOST_DARK}>
              Developer Hub
              <ArrowUpRight size={15} />
            </Link>
          </div>
        </div>

        {/* content row: numbered list + diagram */}
        <div className="grid md:grid-cols-2">
          <div className="border-white/12 py-14 pr-8 md:border-r">
            <div className="flex w-[290px] max-w-full items-center rounded-[13px] bg-[#333231] px-4 py-2.5 text-[18px] font-medium text-white">
              1. Infrastructure
            </div>
            <div className="mt-5 max-w-[420px]">
              <p className="text-[14px] leading-[1.6] text-white/70">
                Ingest multimodal data through a single pipeline at ~60x real-time speed. Index an
                hour of video in a minute. 10k+ hours per day.
              </p>
              <Link
                to="/build"
                className="mt-5 inline-flex items-center gap-1.5 rounded-[14px] border border-white/70 px-3.5 py-1.5 text-[13px] font-medium text-[#f4f3f3] transition hover:bg-white/10"
              >
                Learn more
                <ArrowUpRight size={14} />
              </Link>
            </div>
            <div className="mt-12 space-y-7 text-[18px] font-medium text-white/55">
              <div>2. API + SDK</div>
              <div>3. MCP</div>
              <div>4. Integrations</div>
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
      <Callout className="left-[34%] top-[7%]" label="SPEED" lines={["~60x real-time ratio:", "~1 min to index 1H video;", "tracking to 100x ratio"]} />
      <Callout className="bottom-[7%] left-[7%]" label="SCALE" lines={["10k+ hrs/day today;", "roadmap to 1M+ hrs/day"]} />
      <Callout className="bottom-[7%] right-[6%]" label="PROPRIETARY" lines={["Patented end-to-end video", "processing + inference system"]} />
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

/* ---------------- capabilities (frosted shell, click-to-swap video) ---------------- */
function Capabilities() {
  const [active, setActive] = useState(0);
  const cap = CAPS[active];
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
            Built for the most demanding video workflows.
          </h2>
        </div>
        <div className="flex items-end py-10 md:pl-10">
          <p className="max-w-[440px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
            Designed for organizations working with video at scale, turning raw, passive footage
            into a strategic asset teams can actually use.
          </p>
        </div>
      </div>

      {/* frosted interactive shell */}
      <div className="mt-12 overflow-hidden rounded-[48px] border border-[var(--color-chalk)] bg-white/55 shadow-card backdrop-blur">
        <div className="grid items-center md:grid-cols-[0.82fr_1.18fr]">
          <div className="p-8 md:p-12">
            {CAPS.map((c, i) => {
              const on = i === active;
              return (
                <button
                  key={c.title}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setActive(i)}
                  className="block w-full cursor-pointer border-0 bg-transparent py-3.5 text-left"
                >
                  <h3
                    className={
                      "text-[22px] font-medium tracking-[-0.3px] transition " +
                      (on ? "text-[var(--color-obsidian)]" : "text-[var(--color-obsidian)]/45 hover:text-[var(--color-obsidian)]/70")
                    }
                  >
                    {c.title}
                  </h3>
                  {on && (
                    <p className="mt-3 max-w-[430px] text-[14px] leading-[1.6] text-[var(--color-gravel)]">{c.body}</p>
                  )}
                </button>
              );
            })}
          </div>
          <div className="flex items-center justify-center p-6 md:py-10 md:pr-10">
            <video
              key={cap.v}
              src={`/twelvelabs/${cap.v}.webm`}
              autoPlay
              muted
              loop
              playsInline
              preload="auto"
              className="w-full max-w-[600px] object-contain"
            />
          </div>
        </div>
      </div>
      </Container>
    </section>
  );
}

/* ---------------- metrics + trusted by ---------------- */
function Metrics() {
  return (
    <Container className="py-20">
      <div className="grid gap-8 md:grid-cols-2">
        <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
          Create, scale and move faster with video.
        </h2>
        <p className="max-w-[440px] self-end text-[15px] leading-[1.6] text-[var(--color-gravel)]">
          Built to handle petabytes of multimodal data, with retrieval and reasoning benchmarked
          against the best general-purpose models.
        </p>
      </div>

      <div className="mt-12 grid gap-px overflow-hidden rounded-[16px] border border-[var(--color-chalk)] bg-[var(--color-chalk)] sm:grid-cols-3">
        {METRICS.map((m) => (
          <div key={m.value} className="bg-[var(--color-eggshell)] p-8">
            <div className="text-[48px] font-medium leading-none tracking-[-1.5px] tabular-nums text-[var(--color-obsidian)]">
              {m.value}
            </div>
            <p className="mt-4 max-w-[260px] text-[14px] leading-[1.5] text-[var(--color-gravel)]">{m.label}</p>
          </div>
        ))}
      </div>

      <div className="mt-16">
        <p className="text-center text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-slate)]">
          Built on open infrastructure
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
  const [active, setActive] = useState(1);
  const trackRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const [tx, setTx] = useState(0);

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
              Built for every video workflow.
            </h2>
          </div>
          <div className="flex items-end py-10 md:pl-10">
            <p className="max-w-[440px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
              Video intelligence for teams in media, sports, advertising, government, security and more.
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
                  Learn more
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
              alt="Encrypted, access-controlled video stack"
              loading="lazy"
              className="w-full max-w-[560px] object-contain"
            />
          </div>
          <div className="md:border-l md:border-[var(--color-obsidian)]/15 md:pl-12">
            <h2 className="text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">Secure by design</h2>
            <p className="mt-5 max-w-[420px] text-[15px] leading-[1.6] text-[var(--color-gravel)]">
              SOC 2 Type II certified. Encrypted data handling. The entire intelligence stack deploys
              where you want.
            </p>
            <Link to="/solutions#security" className={`mt-7 ${GHOST_LIGHT}`}>
              Learn more
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
  return (
    <Container className="py-20">
      <h2 className="max-w-[640px] text-[32px] font-medium leading-[1.08] tracking-[-0.8px] md:text-[44px]">
        Video-native perception and reasoning.
      </h2>
      <div className="mt-10 grid gap-5 md:grid-cols-2">
        {MODELS.map((m) => (
          <div key={m.open} className="rounded-[24px] border border-[var(--color-chalk)] bg-white p-8">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]">{m.kind}</p>
            <h3 className="mt-3 text-[24px] font-medium tracking-[-0.4px]">{m.name}</h3>
            <span className="mt-2 inline-flex rounded-md bg-[var(--color-powder)] px-2 py-0.5 font-mono text-[12px] text-[var(--color-gravel)]">
              {m.open}
            </span>
            <p className="mt-4 text-[14px] leading-[1.6] text-[var(--color-gravel)]">{m.body}</p>
            <Link to="/product/product-overview" className="mt-5 inline-flex items-center gap-1 text-[14px] font-medium text-[var(--color-accent-blue)] hover:gap-1.5">
              Learn more
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
  return (
    <Container className="pb-24 pt-8">
      <div id="cta" className="rounded-[32px] bg-gradient-warm px-8 py-20 text-center md:py-24">
        <h2 className="mx-auto max-w-[760px] text-[36px] font-medium leading-[1.05] tracking-[-1px] text-[var(--color-obsidian)] md:text-[52px]">
          Ready to see what your archive actually knows?
        </h2>
        <p className="mx-auto mt-5 max-w-[520px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          Try it in the Playground, or talk to our team. No credit card required.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link to="/signup" className={FILLED}>
            Start building
            <ArrowUpRight size={16} />
          </Link>
          <Link to="/pricing" className={GHOST_LIGHT}>
            Talk to sales
          </Link>
        </div>
      </div>
    </Container>
  );
}

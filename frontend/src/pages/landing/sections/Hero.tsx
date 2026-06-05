import { Link } from "react-router";
import { HeroDemo } from "./HeroDemo";

/**
 * Scattered video-thumbnail motif drifting behind the hero (TwelveLabs
 * signature, on a light canvas). Reuses the existing /twelvelabs frames.
 * Decorative only (aria-hidden); a radial white vignette keeps the centre
 * clear so the headline + demo card stay readable. Drift is disabled under
 * prefers-reduced-motion (see index.css).
 */
const MOTIF: { src: string; cls: string; x: string; y: string; dur: string }[] = [
  { src: "/twelvelabs/search.png",    cls: "left-[2%]  top-[10%] w-[150px] rotate-[-6deg]", x: "8px",  y: "-26px", dur: "12s" },
  { src: "/twelvelabs/analyze.png",   cls: "left-[14%] top-[46%] w-[120px] rotate-[4deg]",  x: "-6px", y: "-18px", dur: "10s" },
  { src: "/twelvelabs/embed-bg.png",  cls: "left-[6%]  top-[74%] w-[170px] rotate-[3deg]",  x: "10px", y: "-30px", dur: "14s" },
  { src: "/twelvelabs/analyze-bg.png",cls: "right-[3%] top-[8%]  w-[180px] rotate-[5deg]",  x: "-10px",y: "-24px", dur: "13s" },
  { src: "/twelvelabs/search-bg.jpg", cls: "right-[12%]top-[44%] w-[130px] rotate-[-5deg]", x: "8px",  y: "-20px", dur: "11s" },
  { src: "/twelvelabs/embed.png",     cls: "right-[5%] top-[72%] w-[150px] rotate-[-3deg]", x: "-8px", y: "-28px", dur: "15s" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-[var(--color-eggshell)]">
      {/* drifting thumbnail motif */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        {MOTIF.map((m, i) => (
          <img
            key={i}
            src={m.src}
            alt=""
            loading="lazy"
            className={`hero-drift absolute hidden rounded-2xl border border-black/5 object-cover opacity-45 shadow-[0_20px_50px_-25px_rgba(0,0,0,0.4)] lg:block ${m.cls}`}
            style={
              {
                aspectRatio: "16 / 10",
                "--drift-x": m.x,
                "--drift-y": m.y,
                "--drift-dur": m.dur,
              } as React.CSSProperties
            }
          />
        ))}
        {/* white vignette so the centre column stays clean/legible */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(70% 60% at 50% 38%, rgba(253,252,252,0.92) 0%, rgba(253,252,252,0.7) 45%, rgba(253,252,252,0.2) 100%)",
          }}
        />
      </div>

      {/* foreground content */}
      <div className="relative mx-auto max-w-[1280px] px-6 pt-20 pb-16 text-center md:pt-24">
        <p className="mb-5 text-[13px] uppercase tracking-[0.18em] text-[var(--color-gravel)]">
          Video AI Platform
        </p>
        <h1 className="mx-auto max-w-[920px] text-[52px] font-light leading-[1.04] tracking-[-1.5px] text-[var(--color-obsidian)] md:text-[68px]">
          See the unseen in every video.
        </h1>
        <p className="mx-auto mt-7 max-w-[640px] text-[16px] leading-[1.55] text-[var(--color-gravel)] md:text-[17px]">
          Search, chat with, and segment your footage in natural language. State-of-the-art
          video understanding turns hours of raw video into searchable, answerable, AI-ready
          moments.
        </p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/signup"
            className="inline-flex h-11 cursor-pointer items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]"
          >
            Start free ↗
          </Link>
          <a
            href="#cta"
            className="inline-flex h-11 cursor-pointer items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
          >
            Talk to sales
          </a>
        </div>

        {/* try-before-signup interactive demo */}
        <HeroDemo />
      </div>
    </section>
  );
}

import { useEffect, useRef } from "react";
import { Link } from "react-router";

export function Hero() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    el.muted = true;
    el.playsInline = true;
    void el.play().catch(() => {});
  }, []);

  return (
    <section className="mx-auto max-w-[1280px] px-6 pt-20 pb-12 text-center md:pt-24">
      <p className="mb-5 text-[13px] uppercase tracking-[0.18em] text-[var(--color-gravel)]">
        Video AI Platform
      </p>
      <h1 className="mx-auto max-w-[920px] text-[52px] font-light leading-[1.04] tracking-[-1.5px] text-[var(--color-obsidian)] md:text-[68px]">
        For everything you want to do with video.
      </h1>
      <p className="mx-auto mt-7 max-w-[640px] text-[16px] leading-[1.55] text-[var(--color-gravel)] md:text-[17px]">
        Build features like semantic search and content recommenders, or novel applications that
        redefine what's possible. Our state-of-the-art AI video understanding unlocks your video's
        full potential.
      </p>
      <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
        <Link
          to="/signup"
          className="inline-flex h-11 items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition hover:bg-neutral-800"
        >
          Go to Playground ↗
        </Link>
        <a
          href="#cta"
          className="inline-flex h-11 items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
        >
          Talk to sales
        </a>
      </div>

      {/* Hero video showcase — green halo glow + rounded card */}
      <div className="relative mx-auto mt-16 max-w-[1180px]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -m-6 rounded-[40px] opacity-90 blur-2xl"
          style={{
            background:
              "linear-gradient(135deg, rgba(168, 230, 178, 0.85) 0%, rgba(220, 240, 130, 0.75) 50%, rgba(168, 230, 178, 0.85) 100%)",
          }}
        />
        <div className="relative overflow-hidden rounded-[32px] border border-white/40 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.25)]">
          <video
            ref={videoRef}
            src="/twelvelabs/hero.mp4"
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            className="block w-full aspect-[16/9] object-cover"
          />
        </div>
      </div>
    </section>
  );
}

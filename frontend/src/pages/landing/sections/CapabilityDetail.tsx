import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router";
import { cn } from "@/lib/utils";

interface Props {
  eyebrow: string;
  /** Optional icon shown to the left of the eyebrow label. */
  eyebrowIcon?: ReactNode;
  title: string;
  body: string;
  ctaTo: string;
  ctaLabel?: string;
  /** Static image used as the section artwork sitting below the text. */
  backgroundImage?: string;
  /** Looping video used as the section artwork sitting below the text. */
  backgroundVideo?: string;
  /** Poster frame shown before the video can play / as fallback. */
  videoPoster?: string;
  /** Tint for the eyebrow + body text so it matches the palette. */
  toneClass?: string;
}

/**
 * TwelveLabs-style capability section. The artwork fills the entire section
 * as a full-bleed background (matching `object-fit: cover` from the reference
 * markup) while the eyebrow + title + body + CTAs overlay it centered.
 *
 * The reference illustrations are designed with their content labels
 * ("Create summary", "Analyze content", "IMAGE/AUDIO/VIDEO/TEXT", etc.) at
 * the peripheral edges so that a centered text card never occludes them.
 */
export function CapabilityDetail({
  eyebrow,
  eyebrowIcon,
  title,
  body,
  ctaTo,
  ctaLabel = "Try on Playground",
  backgroundImage,
  backgroundVideo,
  videoPoster,
  toneClass = "text-[var(--color-gravel)]",
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    el.muted = true;
    el.playsInline = true;
    void el.play().catch(() => {
      /* autoplay may still be blocked; poster covers that case. */
    });
  }, [backgroundVideo]);

  return (
    <section className="relative w-full overflow-hidden">
      {/* Maintain a 16:9-ish aspect ratio so the artwork's edge labels stay visible */}
      <div className="relative w-full" style={{ aspectRatio: "1840 / 1100" }}>
        {/* Full-bleed artwork — object-cover matches the framer reference */}
        {backgroundVideo ? (
          <>
            {videoPoster && (
              <img
                src={videoPoster}
                alt=""
                aria-hidden="true"
                className="absolute inset-0 h-full w-full object-cover"
              />
            )}
            <video
              ref={videoRef}
              src={backgroundVideo}
              autoPlay
              muted
              loop
              playsInline
              preload="auto"
              poster={videoPoster}
              className="absolute inset-0 h-full w-full object-cover"
              aria-hidden="true"
            />
          </>
        ) : backgroundImage ? (
          <img
            src={backgroundImage}
            alt=""
            aria-hidden="true"
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : null}

        {/* Centered text overlay */}
        <div className="absolute inset-x-0 top-0 z-10 mx-auto flex max-w-[820px] flex-col items-center px-6 pt-20 text-center md:pt-28">
          <p
            className={cn(
              "mb-5 inline-flex items-center gap-2 text-[13px] uppercase tracking-[0.18em]",
              toneClass,
            )}
          >
            {eyebrowIcon ? (
              <span className="inline-flex items-center" aria-hidden="true">
                {eyebrowIcon}
              </span>
            ) : (
              <span aria-hidden="true">✦</span>
            )}
            {eyebrow}
          </p>
          <h2 className="max-w-[760px] text-[40px] font-light leading-[1.08] tracking-[-0.8px] text-[var(--color-obsidian)] md:text-[52px]">
            {title}
          </h2>
          <p className={cn("mt-6 max-w-[560px] text-[15px] leading-[1.55]", toneClass)}>
            {body}
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              to={ctaTo}
              className="inline-flex h-10 items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-5 text-[13px] font-medium text-white transition hover:bg-neutral-800"
            >
              Learn more ↗
            </Link>
            <Link
              to={ctaTo}
              className="inline-flex h-10 items-center rounded-full border border-[var(--color-chalk)] bg-white/90 px-5 text-[13px] font-medium text-[var(--color-obsidian)] backdrop-blur transition hover:bg-white"
            >
              {ctaLabel}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

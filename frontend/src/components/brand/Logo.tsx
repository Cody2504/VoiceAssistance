import { useId } from "react";
import { cn } from "@/lib/utils";

interface Props {
  size?: "sm" | "md";
  className?: string;
}

/**
 * Jockey logo — "Scene Finder" mark: camera viewfinder brackets framing a play
 * triangle ("find any scene"), blue→violet gradient. Rendered inline as SVG so
 * it scales crisply and themes anywhere; the "Jockey" wordmark inherits
 * currentColor, so it reads on both light and dark surfaces.
 */
export function Logo({ size = "md", className }: Props) {
  const gid = useId();
  const px = size === "sm" ? 24 : 28;
  const text = size === "sm" ? "text-base" : "text-lg";
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold leading-none tracking-tight", text, className)}>
      <svg
        width={px}
        height={px}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        <defs>
          <linearGradient id={gid} x1="6" y1="6" x2="42" y2="42" gradientUnits="userSpaceOnUse">
            <stop stopColor="#2563eb" />
            <stop offset="1" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
        <g
          stroke={`url(#${gid})`}
          strokeWidth="3.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M7 16 V9 a2 2 0 0 1 2-2 h7" />
          <path d="M41 16 V9 a2 2 0 0 0-2-2 h-7" />
          <path d="M7 32 v7 a2 2 0 0 0 2 2 h7" />
          <path d="M41 32 v7 a2 2 0 0 1-2 2 h-7" />
        </g>
        <path d="M20 17.5 L31 24 L20 30.5 Z" fill={`url(#${gid})`} />
      </svg>
      <span>Jockey</span>
    </span>
  );
}

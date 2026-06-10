import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { formatSeconds } from "@/lib/utils";

export interface TimelineBlock {
  t_start: number;
  t_end: number;
}

export interface TimelineTrack {
  id: string;
  label: string;
  color: { fill: string; stroke: string };
  blocks: TimelineBlock[];
}

interface Props {
  duration: number;
  tracks: TimelineTrack[];
  playhead: number;
  onSeek: (t: number) => void;
  /** Optional: t_start of the block under the playhead per track. */
  activePerTrack?: Record<string, number | null>;
}

/**
 * TwelveLabs-style multi-track timeline. Each track is a row of colored
 * blocks against a grey rail; a red vertical playhead spans all rows.
 * Clicking a block seeks. Clicking the rail also seeks to the click position.
 */
export function MultiTrackTimeline({
  duration,
  tracks,
  playhead,
  onSeek,
  activePerTrack,
}: Props) {
  const { t } = useTranslation();
  const ticks = useMemo(() => {
    if (!duration || duration <= 0) return [] as number[];
    const step =
      duration <= 30 ? 5 : duration <= 60 ? 10 : duration <= 180 ? 30 : 60;
    const out: number[] = [];
    for (let t = 0; t <= duration; t += step) out.push(t);
    return out;
  }, [duration]);

  if (!duration || duration <= 0) {
    return (
      <div className="rounded-[20px] bg-neutral-100 p-6 text-center text-xs text-neutral-500">
        {t("pgkit.timeline.waiting")}
      </div>
    );
  }

  const pct = (t: number) => `${(t / duration) * 100}%`;
  const playheadPct = Math.max(0, Math.min(playhead / duration, 1)) * 100;

  return (
    <div className="rounded-[20px] bg-neutral-100 px-3 pb-5 pt-5">
      {/* Tick labels */}
      <div className="relative mb-1 flex h-3 font-mono text-[10px]">
        {ticks.map((t) => (
          <span
            key={t}
            className="absolute -translate-x-1/2 whitespace-nowrap text-neutral-500"
            style={{ left: pct(t) }}
          >
            {formatSeconds(t)}
          </span>
        ))}
        <span
          className="absolute -translate-x-1/2 whitespace-nowrap text-red-500"
          style={{ left: `${playheadPct}%` }}
        >
          {formatSeconds(playhead)}
        </span>
      </div>

      <div className="relative flex flex-col gap-5">
        {tracks.map((track) => {
          const active = activePerTrack?.[track.id] ?? null;
          return (
            <div key={track.id}>
              <div
                className="relative h-[22px] cursor-pointer rounded-sm"
                style={{ backgroundColor: "rgba(28, 29, 27, 0.08)" }}
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const x = e.clientX - rect.left;
                  onSeek((x / rect.width) * duration);
                }}
              >
                {track.blocks.map((b, i) => {
                  const isActive = active != null && b.t_start === active;
                  return (
                    <button
                      type="button"
                      key={`${track.id}-${i}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSeek(b.t_start);
                      }}
                      className="absolute top-0 h-full rounded-sm transition-[transform]"
                      style={{
                        left: pct(b.t_start),
                        width: pct(Math.max(0.001, b.t_end - b.t_start)),
                        backgroundColor: track.color.fill,
                        borderWidth: 1,
                        borderStyle: "solid",
                        borderColor: isActive ? track.color.stroke : "transparent",
                        backgroundClip: "padding-box",
                      }}
                      aria-label={`${track.label} ${formatSeconds(b.t_start)}–${formatSeconds(b.t_end)}`}
                    />
                  );
                })}
              </div>
              <div className="mt-1 truncate font-mono text-[11px] font-semibold text-neutral-600">
                {track.label}
              </div>
            </div>
          );
        })}

        {/* Playhead */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-1 z-10 w-[2px] bg-red-500"
          style={{
            left: `${playheadPct}%`,
            height: `calc(${tracks.length} * 42px + 4px)`,
          }}
        >
          <div
            className="absolute h-[7px] w-[7px] -translate-x-1/2 bg-red-500"
            style={{
              top: -4,
              left: "50%",
              clipPath: "polygon(0% 0%, 100% 0%, 50% 100%, 50% 100%)",
            }}
          />
        </div>
      </div>
    </div>
  );
}

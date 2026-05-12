import type { GroundResponse } from "@/apis/videos.api";

interface Props {
  duration: number;
  result?: GroundResponse;
  onSeek: (t: number) => void;
}

export function GroundingTimeline({ duration, result, onSeek }: Props) {
  if (!result) {
    return (
      <div className="grid h-16 place-items-center rounded-md border border-neutral-200 bg-neutral-50/50 text-xs text-neutral-400">
        Ask the agent or run grounding to see relevance over time
      </div>
    );
  }

  const maxRel = Math.max(...result.shots.map((s) => s.relevance ?? 0), 0.0001);

  return (
    <div className="relative h-16 rounded-md border border-neutral-200 bg-neutral-50/50 p-2">
      <div className="relative h-full">
        {result.shots.map((s) => {
          const left = (s.t_start / duration) * 100;
          const width = ((s.t_end - s.t_start) / duration) * 100;
          const r = (s.relevance ?? 0) / maxRel;
          return (
            <button
              key={s.idx}
              onClick={() => onSeek(s.t_start)}
              title={`shot ${s.idx} · ${s.t_start.toFixed(1)}–${s.t_end.toFixed(1)}s · ${(s.relevance ?? 0).toFixed(2)}`}
              className="absolute bottom-0 cursor-pointer bg-neutral-900/80 transition hover:bg-neutral-700"
              style={{
                left: `${left}%`,
                width: `${Math.max(width, 0.5)}%`,
                height: `${r * 100}%`,
              }}
            />
          );
        })}
        {result.spans.map((span, i) => {
          const left = (span.t_start / duration) * 100;
          const width = ((span.t_end - span.t_start) / duration) * 100;
          return (
            <div
              key={i}
              className="pointer-events-none absolute top-0 h-full border-x-2 border-emerald-500 bg-emerald-500/10"
              style={{ left: `${left}%`, width: `${width}%` }}
            />
          );
        })}
      </div>
    </div>
  );
}

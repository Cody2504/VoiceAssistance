import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";

import { VideoThumb } from "@/components/video/VideoThumb";
import { formatSeconds } from "@/lib/utils";

export interface ClipResult {
  video_id: string;
  shot_idx?: number;
  t_start: number;
  t_end: number;
  /** Full video duration in seconds; used as the badge for parent_video tiles. */
  video_duration_s?: number;
  /** Original filename; rendered under parent_video tiles. */
  original_filename?: string;
  /**
   * How the tile should be presented. "parent_video" = one tile per video,
   * shows full video duration, click plays from t=0. "clip" = one tile per
   * shot, shows shot duration, click plays from t_start. Default "clip".
   */
  display_mode?: "parent_video" | "clip";
  /** Relevance score 0..1 (grounding moments) — shown as a % beneath the clip
   *  so the user can compare the top-k candidates (top-1 isn't always right). */
  score?: number;
  /** Descriptive text for the clip (VLM caption / ASR snippet / audio tags),
   *  rendered to the RIGHT of the thumbnail in the summary-style moment card. */
  caption?: string;
}

interface Props {
  clips: ClipResult[];
  visible?: number;
  onPreview: (videoId: string, t: number) => void;
}

// Above this many moments in ONE video, the per-moment thumbnail cards become a
// wall of near-identical frames — switch to a compact click-to-seek citation list.
const COMPACT_MOMENTS_THRESHOLD = 3;

/**
 * Renders the results the agent returns from search / grounding / sounds tools.
 *
 * Three layouts:
 *  - Many "clip" moments in ONE video → a compact **citation list** (click-to-seek
 *    timestamp chip + snippet text, no per-row thumbnails) — easy to scan.
 *  - A few "clip" moments, or moments spanning multiple videos → summary-style
 *    cards (thumbnail left, caption + click-to-seek timestamp right).
 *  - "parent_video" results ("find videos like this") → the 3-column thumbnail grid.
 */
export function VideoSearchResults({ clips, visible = 3, onPreview }: Props) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  if (clips.length === 0) return null;

  const moments = clips.filter((c) => c.display_mode !== "parent_video");
  const tiles = clips.filter((c) => c.display_mode === "parent_video");
  const compact =
    moments.length > COMPACT_MOMENTS_THRESHOLD &&
    new Set(moments.map((c) => c.video_id)).size === 1;

  const sliceWithMore = <T,>(arr: T[], limit: number) => {
    const shown = expanded ? arr : arr.slice(0, limit);
    return { shown, extra: arr.length - shown.length };
  };

  const moreButton = (extra: number) =>
    !expanded && extra > 0 ? (
      <button
        onClick={() => setExpanded(true)}
        className="inline-flex items-center gap-1 text-sm font-medium text-emerald-600 hover:text-emerald-700"
      >
        {t(extra === 1 ? "chat.search_results.see_more_one" : "chat.search_results.see_more_other", { count: extra })}
        <ChevronDown size={14} />
      </button>
    ) : null;

  const timestampChip = (c: ClipResult) => (
    <button
      onClick={() => onPreview(c.video_id, c.t_start)}
      className="shrink-0 rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium tabular-nums text-emerald-700 hover:bg-emerald-100"
    >
      {formatSeconds(c.t_start)}–{formatSeconds(c.t_end)}
    </button>
  );

  // compact moments shown a bit denser than card moments
  const momentSlice = sliceWithMore(moments, compact ? Math.max(visible, 5) : visible);
  const tileSlice = sliceWithMore(tiles, visible);

  return (
    <div className="space-y-3">
      {moments.length > 0 && compact && (
        <div className="space-y-1.5 border-l-2 border-neutral-200 pl-3">
          {momentSlice.shown.map((c, i) => (
            <div key={`${c.video_id}:${c.shot_idx ?? i}`} className="flex items-start gap-2 text-sm leading-relaxed">
              {timestampChip(c)}
              {c.caption ? (
                <span className="text-neutral-700">{c.caption}</span>
              ) : c.score !== undefined ? (
                <span className="pt-0.5 text-xs text-neutral-400">{Math.round(c.score * 100)}%</span>
              ) : null}
            </div>
          ))}
          {moreButton(momentSlice.extra)}
        </div>
      )}

      {moments.length > 0 && !compact && (
        <div className="divide-y divide-neutral-100">
          {momentSlice.shown.map((c, i) => (
            <div key={`${c.video_id}:${c.shot_idx ?? i}`} className="grid grid-cols-[200px_1fr] items-start gap-4 py-2">
              <div className="space-y-1">
                <VideoThumb
                  videoId={c.video_id}
                  shotIdx={c.shot_idx}
                  duration={c.t_end - c.t_start}
                  onClick={() => onPreview(c.video_id, c.t_start)}
                  className="aspect-video"
                />
                {c.original_filename && (
                  <p className="truncate text-xs text-neutral-500" title={c.original_filename}>
                    {c.original_filename}
                  </p>
                )}
              </div>
              <div className="space-y-1.5 text-sm leading-relaxed text-neutral-800">
                {c.caption && <p className="[&_p]:my-0">{c.caption}</p>}
                <div className="flex items-center gap-2 text-xs">
                  {timestampChip(c)}
                  {c.score !== undefined && (
                    <span className="font-medium text-neutral-500">{Math.round(c.score * 100)}%</span>
                  )}
                </div>
              </div>
            </div>
          ))}
          {moreButton(momentSlice.extra)}
        </div>
      )}

      {tiles.length > 0 && (
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-3">
            {tileSlice.shown.map((c, i) => (
              <div key={`${c.video_id}:${c.shot_idx ?? i}`} className="space-y-1">
                <VideoThumb
                  videoId={c.video_id}
                  shotIdx={c.shot_idx}
                  duration={typeof c.video_duration_s === "number" ? c.video_duration_s : undefined}
                  onClick={() => onPreview(c.video_id, 0)}
                  className="aspect-video"
                />
                {c.original_filename && (
                  <p className="truncate text-xs text-neutral-700" title={c.original_filename}>
                    {c.original_filename}
                  </p>
                )}
              </div>
            ))}
          </div>
          {moreButton(tileSlice.extra)}
        </div>
      )}
    </div>
  );
}

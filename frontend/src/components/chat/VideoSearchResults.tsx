import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { VideoThumb } from "@/components/video/VideoThumb";

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
}

interface Props {
  clips: ClipResult[];
  visible?: number;
  onPreview: (videoId: string, t: number) => void;
}

/**
 * Renders the row of clickable thumbnails the agent returns from search/grounding tools.
 * Parent-video results render with the full video duration and play from t=0; clip
 * results render with the shot window and play from t_start.
 */
export function VideoSearchResults({ clips, visible = 3, onPreview }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (clips.length === 0) return null;

  const shown = expanded ? clips : clips.slice(0, visible);
  const extra = clips.length - visible;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-3">
        {shown.map((c, i) => {
          const isParent = c.display_mode === "parent_video";
          const badge = isParent ? c.video_duration_s : c.t_end - c.t_start;
          const playAt = isParent ? 0 : c.t_start;
          return (
            <div key={`${c.video_id}:${c.shot_idx ?? i}`} className="space-y-1">
              <VideoThumb
                videoId={c.video_id}
                shotIdx={c.shot_idx}
                duration={typeof badge === "number" ? badge : undefined}
                onClick={() => onPreview(c.video_id, playAt)}
                className="aspect-video"
              />
              {isParent && c.original_filename && (
                <p className="truncate text-xs text-neutral-700" title={c.original_filename}>
                  {c.original_filename}
                </p>
              )}
            </div>
          );
        })}
      </div>
      {!expanded && extra > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="inline-flex items-center gap-1 text-sm font-medium text-emerald-600 hover:text-emerald-700"
        >
          See {extra} more {extra === 1 ? "result" : "results"}
          <ChevronDown size={14} />
        </button>
      )}
    </div>
  );
}

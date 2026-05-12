import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { VideoThumb } from "@/components/video/VideoThumb";

export interface ClipResult {
  video_id: string;
  shot_idx?: number;
  t_start: number;
  t_end: number;
}

interface Props {
  clips: ClipResult[];
  visible?: number;
  onPreview: (videoId: string, t: number) => void;
}

/**
 * Renders the row of clickable thumbnails the agent returns from search/grounding tools.
 * Mirrors the "Find me 5 clips of …" screenshot — show first N, "See M more results ▼" reveals the rest.
 */
export function VideoSearchResults({ clips, visible = 3, onPreview }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (clips.length === 0) return null;

  const shown = expanded ? clips : clips.slice(0, visible);
  const extra = clips.length - visible;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-3">
        {shown.map((c, i) => (
          <VideoThumb
            key={`${c.video_id}:${c.shot_idx ?? i}`}
            videoId={c.video_id}
            shotIdx={c.shot_idx}
            duration={c.t_end - c.t_start}
            onClick={() => onPreview(c.video_id, c.t_start)}
            className="aspect-video"
          />
        ))}
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

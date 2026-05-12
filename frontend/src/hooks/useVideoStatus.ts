import { useEffect, useRef, useState } from "react";
import { getVideo, type VideoSummary } from "@/apis/videos.api";

export function useVideoStatus(id: string | undefined, initial?: VideoSummary) {
  const [video, setVideo] = useState<VideoSummary | undefined>(initial);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;

    const tick = async () => {
      try {
        const v = await getVideo(id);
        if (!alive) return;
        setVideo(v);
        if (v.status === "queued" || v.status === "processing") {
          timer.current = window.setTimeout(tick, 3000);
        }
      } catch {
        /* ignore — surfaced upstream */
      }
    };
    tick();

    return () => {
      alive = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [id]);

  return video;
}

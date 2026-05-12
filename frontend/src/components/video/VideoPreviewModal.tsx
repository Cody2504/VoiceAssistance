import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { getStreamUrl } from "@/apis/videos.api";

interface Props {
  open: boolean;
  videoId: string | null;
  startAt?: number;
  onClose: () => void;
}

export function VideoPreviewModal({ open, videoId, startAt, onClose }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!open || !videoId) { setUrl(null); return; }
    let alive = true;
    getStreamUrl(videoId).then((u) => { if (alive) setUrl(u); }).catch(() => setUrl(null));
    return () => { alive = false; };
  }, [open, videoId]);

  useEffect(() => {
    if (videoRef.current && url && startAt !== undefined) {
      videoRef.current.currentTime = startAt;
      videoRef.current.play().catch(() => {});
    }
  }, [url, startAt]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-3xl overflow-hidden rounded-lg bg-black"
      >
        <button onClick={onClose} className="absolute right-3 top-3 z-10 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80">
          <X size={16} />
        </button>
        {url ? (
          <video ref={videoRef} src={url} controls autoPlay className="aspect-video w-full" />
        ) : (
          <div className="aspect-video w-full grid place-items-center text-neutral-400">Loading…</div>
        )}
      </div>
    </div>
  );
}

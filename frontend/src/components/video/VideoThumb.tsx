import { useState } from "react";
import { cn, formatSeconds } from "@/lib/utils";
import { ROUTES } from "@/constants/routes";
import { API_BASE_URL } from "@/config";

interface Props {
  videoId: string;
  shotIdx?: number;
  duration?: number;
  fallback?: string;
  onClick?: () => void;
  className?: string;
  draggable?: boolean;
  onDragStart?: (e: React.DragEvent) => void;
}

/**
 * Renders a thumbnail for a (video, shot?) pair.
 * Source URL points at `thumbs/{video_id}/{shot_idx}.jpg` in MinIO via the gateway.
 * Falls back to a neutral block when the thumb hasn't been generated yet.
 */
export function VideoThumb({
  videoId, shotIdx, duration, fallback, onClick, className, draggable, onDragStart,
}: Props) {
  const [errored, setErrored] = useState(false);
  // The video-service exposes thumbnails via a presigned URL endpoint;
  // for now we point at the gateway's /api/v1/videos/{id}/stream when no shot is given,
  // and at a hypothetical /thumbs/{id}/{idx}.jpg path otherwise.
  const src = shotIdx !== undefined
    ? `${API_BASE_URL}/videos/${videoId}/thumb/${shotIdx}`
    : `${API_BASE_URL}${ROUTES.VIDEO_STREAM(videoId)}#t=0.1`;

  return (
    <div
      onClick={onClick}
      draggable={draggable}
      onDragStart={onDragStart}
      className={cn(
        "group relative overflow-hidden rounded-md bg-neutral-200 ring-1 ring-neutral-200 transition",
        onClick && "cursor-pointer hover:ring-neutral-400",
        className,
      )}
    >
      {!errored && (
        <img
          src={src}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setErrored(true)}
          draggable={false}
        />
      )}
      {errored && (
        <div className="grid h-full w-full place-items-center text-xs text-neutral-500">
          {fallback ?? "video"}
        </div>
      )}
      {duration !== undefined && (
        <span className="duration-badge">{formatSeconds(duration)}</span>
      )}
    </div>
  );
}

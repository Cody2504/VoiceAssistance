import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn, formatSeconds } from "@/lib/utils";
import { getThumbUrl } from "@/apis/videos.api";

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
 *
 * The thumb endpoint is auth-guarded and returns ``{url}`` to a presigned MinIO
 * object (an ``<img src>`` tag can't carry the Bearer token, so we resolve the URL
 * via an authed XHR first and then point ``<img>`` at the presigned URL itself).
 * When ``shotIdx`` is omitted we default to the first shot, which is how the
 * library tiles get a cover thumbnail.
 */
export function VideoThumb({
  videoId, shotIdx, duration, fallback, onClick, className, draggable, onDragStart,
}: Props) {
  const { t } = useTranslation();
  const effectiveIdx = shotIdx ?? 0;
  const [src, setSrc] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let alive = true;
    setSrc(null);
    setErrored(false);
    getThumbUrl(videoId, effectiveIdx)
      .then((u) => { if (alive) setSrc(u); })
      .catch(() => { if (alive) setErrored(true); });
    return () => { alive = false; };
  }, [videoId, effectiveIdx]);

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
      {src && !errored && (
        <img
          src={src}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setErrored(true)}
          draggable={false}
        />
      )}
      {(!src || errored) && (
        <div className="grid h-full w-full place-items-center text-xs text-neutral-500">
          {fallback ?? t("console.thumb.fallback")}
        </div>
      )}
      {duration !== undefined && (
        <span className="duration-badge">{formatSeconds(duration)}</span>
      )}
    </div>
  );
}

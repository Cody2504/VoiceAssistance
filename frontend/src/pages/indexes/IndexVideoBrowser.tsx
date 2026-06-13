import { useEffect, useMemo, useRef, useState } from "react";
import { Hourglass, Play, SquareArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { listIndexVideos, type IndexVideoEntry } from "@/apis/indexes.api";
import { getStreamUrl, listVideos } from "@/apis/videos.api";
import { VideoThumb } from "@/components/video/VideoThumb";
import { cn } from "@/lib/utils";
import { IndexVideoPreviewModal } from "./IndexVideoPreviewModal";

const PAGE_SIZE = 12;

function fmtUsage(totalS: number): string {
  const h = Math.floor(totalS / 3600);
  const m = Math.round((totalS % 3600) / 60);
  if (h > 0) return `${h} hr ${m} min`;
  if (m > 0) return `${m} min`;
  return `${Math.round(totalS)} sec`;
}

/** TwelveLabs-style page list: 1 2 3 4 5 … N with a sliding window. */
function pageWindow(current: number, total: number): Array<number | "…"> {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

/** A video card that shows a static thumbnail and plays a muted preview on hover
 *  (the stream URL is fetched lazily, only the first time the card is hovered). */
function HoverVideoCard({
  entry,
  onOpen,
}: {
  entry: IndexVideoEntry;
  onOpen: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!hovered || url) return;
    let alive = true;
    getStreamUrl(entry.video_id)
      .then((u) => {
        if (alive) setUrl(u);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [hovered, url, entry.video_id]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (hovered && url) {
      v.currentTime = 0;
      v.play().catch(() => {});
    } else {
      v.pause();
    }
  }, [hovered, url]);

  return (
    <button type="button" className="group/card text-left" onClick={onOpen}>
      <div
        className="relative aspect-video w-full overflow-hidden rounded-[12px] bg-black"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <VideoThumb videoId={entry.video_id} className="h-full w-full rounded-none bg-transparent ring-0" />
        {url && (
          <video
            ref={videoRef}
            src={url}
            muted
            loop
            playsInline
            preload="none"
            className={cn(
              "absolute inset-0 h-full w-full object-cover transition-opacity duration-200",
              hovered ? "opacity-100" : "opacity-0",
            )}
          />
        )}
        {entry.duration_s != null && (
          <div className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-md border border-white/90 px-1">
            <span className="font-mono text-[11px] text-white">{fmtHMS(entry.duration_s)}</span>
          </div>
        )}
        {entry.status !== "ready" && (
          <span className="absolute right-2 top-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-amber-300">
            {entry.status}
          </span>
        )}
      </div>
      <p
        className="mt-2 truncate text-[12px] text-[var(--color-obsidian)]"
        title={entry.original_filename}
      >
        {entry.original_filename}
      </p>
    </button>
  );
}

function fmtHMS(s: number): string {
  const sec = Math.round(s);
  const h = String(Math.floor(sec / 3600)).padStart(2, "0");
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
  const ss = String(sec % 60).padStart(2, "0");
  return `${h}:${m}:${ss}`;
}

/**
 * Right-pane "browse the selected index" grid for the Search / Analyze pages —
 * mirrors the TwelveLabs reference where picking an index reveals its videos
 * (hover to preview) instead of the example cards. `indexId === "default"`
 * browses the whole library (the virtual default index).
 */
export function IndexVideoBrowser({ indexId }: { indexId: string }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<IndexVideoEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [previewPos, setPreviewPos] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setPage(1);
    const load = async () => {
      try {
        if (indexId === "default") {
          const vids = await listVideos();
          return vids.map<IndexVideoEntry>((v, i) => ({
            video_id: v.id,
            position: i,
            original_filename: v.original_filename,
            duration_s: v.duration_s,
            status: v.status,
          }));
        }
        return await listIndexVideos(indexId);
      } catch {
        return [];
      }
    };
    load().then((rows) => {
      if (alive) {
        setItems(rows);
        setLoading(false);
      }
    });
    return () => {
      alive = false;
    };
  }, [indexId]);

  const totalDuration = useMemo(
    () => items.reduce((s, v) => s + (v.duration_s ?? 0), 0),
    [items],
  );

  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageRows = items.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-x-4 gap-y-6 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i}>
            <div className="aspect-video w-full animate-pulse rounded-[12px] bg-[var(--color-powder)]" />
            <div className="mt-2 h-3 w-3/4 animate-pulse rounded bg-[var(--color-powder)]" />
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--color-chalk)] bg-white/50 p-10 text-center text-[13px] text-[var(--color-gravel)]">
        {t("console.index_detail.empty_hint")}
      </div>
    );
  }

  return (
    <div>
      {/* usage line */}
      <div className="mb-5 flex items-center gap-x-2">
        <div className="flex items-center gap-x-1">
          <Play size={18} className="text-[var(--color-slate)]" />
          <p className="text-[13px] text-[var(--color-gravel)]">
            {t("console.index_detail.videos_meta", { count: items.length })}
          </p>
        </div>
        <div className="h-1 w-1 rounded-full bg-[var(--color-slate)]" />
        <div className="flex items-center gap-x-1">
          <Hourglass size={16} className="text-[var(--color-slate)]" />
          <p className="text-[13px] text-[var(--color-gravel)]">{fmtUsage(totalDuration)}</p>
        </div>
      </div>

      {/* grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-6 lg:grid-cols-3">
        {pageRows.map((entry) => (
          <HoverVideoCard
            key={entry.video_id}
            entry={entry}
            onOpen={() => setPreviewPos(items.indexOf(entry))}
          />
        ))}
      </div>

      {/* pagination */}
      {pageCount > 1 && (
        <div className="mt-8 flex items-center justify-center">
          <div className="flex items-center">
            <button
              disabled={safePage <= 1}
              onClick={() => setPage(safePage - 1)}
              className="flex h-10 w-10 items-center justify-center rounded-2xl text-[var(--color-obsidian)] transition disabled:text-[var(--color-slate)] [&>svg]:h-4 [&>svg]:w-4 enabled:hover:bg-[var(--color-powder)]"
            >
              <SquareArrowRight className="rotate-180" />
            </button>
            {pageWindow(safePage, pageCount).map((p, i) =>
              p === "…" ? (
                <span
                  key={`gap-${i}`}
                  className="flex h-10 w-10 items-center justify-center text-[13px] text-[var(--color-gravel)]"
                >
                  …
                </span>
              ) : (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-2xl text-[13px] text-[var(--color-obsidian)] transition",
                    p === safePage ? "bg-[var(--color-chalk)]" : "hover:bg-[var(--color-powder)]",
                  )}
                >
                  {p}
                </button>
              ),
            )}
            <button
              disabled={safePage >= pageCount}
              onClick={() => setPage(safePage + 1)}
              className="flex h-10 w-10 items-center justify-center rounded-2xl text-[var(--color-obsidian)] transition disabled:text-[var(--color-slate)] [&>svg]:h-4 [&>svg]:w-4 enabled:hover:bg-[var(--color-powder)]"
            >
              <SquareArrowRight />
            </button>
          </div>
        </div>
      )}

      <IndexVideoPreviewModal
        open={previewPos !== null}
        items={items}
        current={previewPos ?? 0}
        onNavigate={(i) => setPreviewPos(i)}
        onClose={() => setPreviewPos(null)}
        onAnalyze={(videoId) => {
          window.location.assign(
            `/playground/analyze?index_id=${indexId}&video_id=${videoId}`,
          );
        }}
      />
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Upload, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { VideoSummary } from "@/apis/videos.api";
import { deleteVideo, listVideos, uploadVideo } from "@/apis/videos.api";
import { VideoThumb } from "@/components/video/VideoThumb";
import { cn, formatSeconds } from "@/lib/utils";

interface Props {
  /** When provided, called when the user clicks (preview) a video. */
  onPreview?: (video: VideoSummary) => void;
}

/**
 * Library grid that doubles as a drag source. Each thumbnail sets a
 * "application/x-video" payload so drop targets (e.g. ChatComposer) can read it.
 */
export function LibraryGrid({ onPreview }: Props) {
  const { t } = useTranslation();
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [uploadPct, setUploadPct] = useState<number | null>(null);

  const refresh = useCallback(async () => setVideos(await listVideos()), []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    try {
      setUploadPct(0);
      await uploadVideo(file, setUploadPct);
      toast.success(t("console.library.upload_queued"));
      await refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? t("console.library.upload_failed");
      toast.error(msg);
    } finally {
      setUploadPct(null);
    }
  }, [refresh, t]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { "video/*": [".mp4", ".mov", ".mkv", ".webm"] }, multiple: false, noClick: true,
  });

  return (
    <div className="flex h-full flex-col">
      <div
        {...getRootProps()}
        className={cn(
          "mb-3 flex items-center justify-between gap-3 rounded-md border border-dashed px-3 py-2 text-xs transition",
          isDragActive ? "border-neutral-900 bg-neutral-50" : "border-neutral-200",
        )}
      >
        <input {...getInputProps()} />
        <span className="flex items-center gap-2 text-neutral-600">
          <Upload size={14} />
          {isDragActive ? t("console.library.drop_active") : t("console.library.drop_hint")}
        </span>
        <button
          type="button"
          onClick={() => (document.querySelector("input[type=file]") as HTMLInputElement | null)?.click()}
          className="rounded-md bg-neutral-900 px-3 py-1 text-xs font-medium text-white transition duration-150 ease-out hover:bg-neutral-700 active:scale-95"
        >
          {t("console.library.upload_btn")}
        </button>
      </div>
      {uploadPct !== null && (
        <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-neutral-100">
          <div className="h-full bg-neutral-900 transition-[width] duration-300 ease-out" style={{ width: `${uploadPct}%` }} />
        </div>
      )}

      <div className="grid flex-1 grid-cols-2 gap-3 overflow-auto pr-1">
        {videos.length === 0 && (
          <div className="col-span-2 grid place-items-center py-10 text-xs text-neutral-400">
            {t("console.library.empty")}
          </div>
        )}
        {videos.map((v) => (
          <article
            key={v.id}
            draggable={v.status === "ready"}
            onDragStart={(e) => {
              e.dataTransfer.setData("application/x-video", JSON.stringify(v));
              e.dataTransfer.effectAllowed = "copy";
            }}
            onClick={() => onPreview?.(v)}
            className={cn(
              "group relative cursor-pointer space-y-2",
              v.status !== "ready" && "opacity-60",
            )}
          >
            <button
              type="button"
              onClick={async (e) => {
                e.stopPropagation();
                if (!window.confirm(t("console.library.delete_confirm", { name: v.original_filename }))) return;
                try {
                  await deleteVideo(v.id);
                  toast.success(t("console.library.deleted"));
                  await refresh();
                } catch (err: unknown) {
                  const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
                    ?? t("console.library.delete_failed");
                  toast.error(msg);
                }
              }}
              aria-label={t("console.library.delete_aria")}
              title={t("console.library.delete_aria")}
              className="absolute right-1.5 top-1.5 z-10 grid h-6 w-6 place-items-center rounded-full bg-black/70 text-white opacity-0 transition group-hover:opacity-100 hover:bg-black/85"
            >
              <Trash2 size={12} />
            </button>
            <VideoThumb
              videoId={v.id}
              duration={v.duration_s ?? undefined}
              fallback={v.original_filename}
              className="aspect-video"
            />
            <div className="space-y-0.5 text-xs leading-tight">
              <p className="truncate text-neutral-900" title={v.original_filename}>
                {v.original_filename}
              </p>
              <p className="text-neutral-500">
                {v.duration_s ? formatSeconds(v.duration_s) : "—"}
                {v.status !== "ready" && <span className="ml-2 uppercase">{v.status}</span>}
              </p>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

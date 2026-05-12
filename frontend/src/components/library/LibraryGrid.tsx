import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Upload } from "lucide-react";

import type { VideoSummary } from "@/apis/videos.api";
import { listVideos, uploadVideo } from "@/apis/videos.api";
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
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [uploadPct, setUploadPct] = useState<number | null>(null);

  const refresh = useCallback(async () => setVideos(await listVideos()), []);

  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 5000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    try {
      setUploadPct(0);
      await uploadVideo(file, setUploadPct);
      toast.success("Upload queued for indexing");
      await refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Upload failed";
      toast.error(msg);
    } finally {
      setUploadPct(null);
    }
  }, [refresh]);

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
          {isDragActive ? "Drop to upload" : "Drag a video here, or use the button →"}
        </span>
        <button
          type="button"
          onClick={() => (document.querySelector("input[type=file]") as HTMLInputElement | null)?.click()}
          className="rounded-md bg-neutral-900 px-3 py-1 text-xs font-medium text-white hover:bg-neutral-700"
        >
          Upload
        </button>
      </div>
      {uploadPct !== null && (
        <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-neutral-100">
          <div className="h-full bg-neutral-900 transition-all" style={{ width: `${uploadPct}%` }} />
        </div>
      )}

      <div className="grid flex-1 grid-cols-2 gap-3 overflow-auto pr-1">
        {videos.length === 0 && (
          <div className="col-span-2 grid place-items-center py-10 text-xs text-neutral-400">
            No videos yet.
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
              "group cursor-pointer space-y-2",
              v.status !== "ready" && "opacity-60",
            )}
          >
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

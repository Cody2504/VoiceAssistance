import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ArrowLeft, Plus, Trash2, Upload, X } from "lucide-react";

import {
  addVideoToIndex,
  getIndex,
  listIndexVideos,
  removeVideoFromIndex,
  type IndexSummary,
  type IndexVideoEntry,
} from "@/apis/indexes.api";
import { listVideos, uploadVideo, type VideoSummary } from "@/apis/videos.api";
import { cn, formatSeconds } from "@/lib/utils";

export default function IndexDetail() {
  const { indexId } = useParams<{ indexId: string }>();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<IndexSummary | null>(null);
  const [items, setItems] = useState<IndexVideoEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  // Names of files currently uploading (HTTP POST in flight or just enqueued).
  // Rendered as placeholder rows below the real index videos so the user sees
  // immediate feedback. Throttling of *processing* is handled by the backend
  // RQ worker replica count, not by the frontend.
  const [uploadingNames, setUploadingNames] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const reload = useCallback(async () => {
    if (!indexId) return;
    setLoading(true);
    setError(null);
    try {
      const [s, v] = await Promise.all([getIndex(indexId), listIndexVideos(indexId)]);
      setSummary(s);
      setItems(v);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load index");
    } finally {
      setLoading(false);
    }
  }, [indexId]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Re-poll while there are videos that haven't finished ingesting yet, so the
  // status badge flips from queued/processing → ready without a manual refresh.
  useEffect(() => {
    if (!items.some((v) => v.status === "queued" || v.status === "processing")) return;
    const t = setTimeout(() => reload(), 5000);
    return () => clearTimeout(t);
  }, [items, reload]);

  const handleRemove = async (videoId: string) => {
    if (!indexId) return;
    if (!confirm("Remove this video from the index?")) return;
    try {
      await removeVideoFromIndex(indexId, videoId);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove video");
    }
  };

  const handleUploadFiles = useCallback(
    async (files: FileList | null) => {
      if (!indexId || !files || files.length === 0) return;
      const list = Array.from(files).filter(
        (f) => f.type.startsWith("video/") || /\.(mp4|mov|webm|mkv)$/i.test(f.name),
      );
      if (list.length === 0) {
        setError("Only video files are accepted.");
        return;
      }
      setError(null);
      setUploadingNames((prev) => [...prev, ...list.map((f) => f.name)]);

      // Fire all uploads in parallel — each POST is short (it just streams to
      // MinIO + enqueues an RQ job). Real processing concurrency is controlled
      // by the number of video-worker replicas draining the Redis queue, NOT
      // by how many uploads we fire here. Browsers cap concurrent connections
      // per origin (~6 in Chrome) which is the only soft limit we need.
      const uploadOne = async (f: File) => {
        try {
          const v = await uploadVideo(f);
          await addVideoToIndex(indexId, v.id);
        } catch (e) {
          setError(
            e instanceof Error
              ? `Upload failed for ${f.name}: ${e.message}`
              : `Upload failed for ${f.name}`,
          );
        } finally {
          setUploadingNames((prev) => prev.filter((n) => n !== f.name));
        }
      };
      await Promise.all(list.map(uploadOne));
      reload();
    },
    [indexId, reload],
  );

  if (!indexId) return null;

  return (
    <div className="mx-auto max-w-[960px] px-8 py-6">
      <div className="mb-4">
        <button
          onClick={() => navigate("/indexes")}
          className="inline-flex items-center gap-1 text-[12px] text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]"
        >
          <ArrowLeft size={12} />
          All indexes
        </button>
      </div>

      <header className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-[28px] font-light tracking-[-0.5px] text-[var(--color-obsidian)]">
            {summary?.title || (loading ? "Loading…" : "Untitled Index")}
          </h1>
          {summary?.description && (
            <p className="mt-1 max-w-[640px] text-[13px] text-[var(--color-gravel)]">
              {summary.description}
            </p>
          )}
          {summary && (
            <p className="mt-2 text-[12px] text-[var(--color-gravel)]">
              {summary.video_count} video{summary.video_count === 1 ? "" : "s"} ·{" "}
              {summary.total_duration_s ? formatSeconds(summary.total_duration_s) : "0s"} ·{" "}
              Created {new Date(summary.created_at).toLocaleDateString()}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*,.mp4,.mov,.webm,.mkv"
            multiple
            hidden
            onChange={(e) => {
              handleUploadFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-chalk)] bg-white px-4 py-1.5 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
          >
            <Upload size={13} />
            Upload to this index
          </button>
          <button
            onClick={() => setAddOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-obsidian)] px-4 py-1.5 text-[13px] text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]"
          >
            <Plus size={13} />
            Add from library
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[13px] text-rose-700">
          {error}
        </div>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!dragOver) setDragOver(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleUploadFiles(e.dataTransfer.files);
        }}
        className={cn(
          "rounded-xl border bg-white transition",
          dragOver ? "border-[var(--color-obsidian)] bg-[var(--color-powder)]" : "border-[var(--color-chalk)]",
        )}
      >
        {items.length === 0 && uploadingNames.length === 0 ? (
          <div className="p-10 text-center text-[13px] text-[var(--color-gravel)]">
            No videos in this index yet. <strong>Upload to this index</strong>, <strong>Add from library</strong>,
            or drop a video file anywhere on this card.
          </div>
        ) : (
          <ul className="divide-y divide-[var(--color-chalk)]">
            {items.map((v) => (
              <li key={v.video_id} className="flex items-center gap-4 px-4 py-3">
                <span className="w-8 font-mono text-[12px] text-[var(--color-gravel)]">#{v.position}</span>
                <div className="min-w-0 flex-1">
                  <Link
                    to={`/video/${v.video_id}`}
                    className="block truncate text-[14px] text-[var(--color-obsidian)] hover:underline"
                  >
                    {v.original_filename}
                  </Link>
                  <span className="font-mono text-[11px] text-[var(--color-gravel)]">
                    {v.duration_s != null ? formatSeconds(v.duration_s) : "—"} ·{" "}
                    <span className={v.status === "ready" ? "text-emerald-600" : v.status === "error" ? "text-rose-600" : "text-amber-600"}>
                      {v.status}
                    </span>
                  </span>
                </div>
                <button
                  onClick={() => handleRemove(v.video_id)}
                  className="rounded p-1 text-[var(--color-gravel)] hover:bg-rose-50 hover:text-rose-600"
                  title="Remove from index"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
            {uploadingNames.map((name) => (
              <li key={`uploading-${name}`} className="flex items-center gap-4 px-4 py-3 opacity-70">
                <span className="w-8 font-mono text-[12px] text-[var(--color-gravel)]">···</span>
                <div className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] text-[var(--color-obsidian)]">{name}</span>
                  <span className="font-mono text-[11px] text-amber-600">uploading…</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <AddVideosModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        existingIds={new Set(items.map((i) => i.video_id))}
        onAdd={async (videoId) => {
          if (!indexId) return;
          await addVideoToIndex(indexId, videoId);
          reload();
        }}
      />
    </div>
  );
}

function AddVideosModal({
  open,
  onClose,
  existingIds,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  existingIds: Set<string>;
  onAdd: (videoId: string) => Promise<void>;
}) {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    listVideos().then(setVideos).catch(() => setVideos([]));
  }, [open]);

  const available = useMemo(
    () => videos.filter((v) => v.status === "ready" && !existingIds.has(v.id)),
    [videos, existingIds],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-6" onClick={onClose}>
      <div
        className="flex max-h-[80vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
          <h2 className="text-[15px] font-semibold text-neutral-900">Add videos to this index</h2>
          <button onClick={onClose} className="rounded p-1 text-[var(--color-gravel)] hover:bg-neutral-100">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {available.length === 0 && (
            <div className="m-4 rounded-[14px] border border-dashed border-neutral-300 bg-neutral-50 p-6 text-center text-[13px] text-neutral-600">
              No ready videos to add. Upload some on the Assets page first.
            </div>
          )}
          {available.map((v) => (
            <button
              key={v.id}
              type="button"
              disabled={busyId === v.id}
              onClick={async () => {
                setBusyId(v.id);
                try {
                  await onAdd(v.id);
                } finally {
                  setBusyId(null);
                }
              }}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-lg px-4 py-2.5 text-left text-[13px] transition hover:bg-neutral-100 disabled:opacity-50",
              )}
            >
              <span className="min-w-0 flex-1 truncate text-neutral-900">{v.original_filename}</span>
              <span className="font-mono text-[11px] text-neutral-500">
                {v.duration_s != null ? formatSeconds(v.duration_s) : "—"}
              </span>
              <Plus size={14} className="text-neutral-700" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

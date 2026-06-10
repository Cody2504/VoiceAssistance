import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Check, RefreshCw, UploadCloud, Video as VideoIcon, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { listVideos, type VideoSummary } from "@/apis/videos.api";
import { cn, formatSeconds } from "@/lib/utils";

interface Props {
  selectedId?: string;
  onSelect: (v: VideoSummary | null) => void;
  variant?: "panel" | "compact";
  emptyLabel?: string;
}

/**
 * Shared cache + hook so the picker, header buttons, and any other consumer
 * read from one list instead of each making their own request. Returns a
 * `refresh()` so callers can re-fetch on demand (e.g. when the modal opens
 * — covers the "I just uploaded but it isn't here" case).
 */
export function useVideoLibrary() {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchedOnce = useRef(false);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    listVideos()
      .then((list) => setVideos(list.filter((v) => v.status === "ready")))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load videos"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (fetchedOnce.current) return;
    fetchedOnce.current = true;
    refresh();
  }, [refresh]);

  return { videos, loading, error, refresh };
}

/**
 * Single-video selector. The "panel" variant matches the TwelveLabs reference:
 * a gradient-warm card with a "Select a video" pill that opens a centered modal
 * listing the user's ready videos. The "compact" variant falls back to a
 * dropdown row for inline use.
 */
export function VideoPicker({
  selectedId,
  onSelect,
  variant = "panel",
  emptyLabel,
}: Props) {
  const { t } = useTranslation();
  const resolvedEmptyLabel = emptyLabel ?? t("pgkit.video_picker.select_label");
  const { videos, loading, error } = useVideoLibrary();
  const [open, setOpen] = useState(false);

  const selected = videos.find((v) => v.id === selectedId) ?? null;

  if (variant === "compact") {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-10 w-full items-center justify-between gap-2 rounded-md border border-[var(--color-chalk)] bg-white px-3 text-sm transition hover:border-[var(--color-gravel)] focus:outline-none"
      >
        <span className="flex min-w-0 items-center gap-2">
          <VideoIcon className="h-4 w-4 shrink-0 text-[var(--color-gravel)]" />
          <span className="truncate text-[var(--color-obsidian)]">
            {selected ? selected.original_filename : loading ? t("actions.loading") : resolvedEmptyLabel}
          </span>
        </span>
        {selected && (
          <span className="font-mono text-[10px] text-[var(--color-gravel)]">{t("pgkit.video_picker.change_compact")}</span>
        )}
        <VideoPickerModal
          open={open}
          onClose={() => setOpen(false)}
          videos={videos}
          loading={loading}
          error={error}
          selectedId={selectedId}
          onSelect={(v) => {
            onSelect(v);
            setOpen(false);
          }}
        />
      </button>
    );
  }

  // panel variant
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="relative flex h-[230px] w-full items-center justify-center overflow-hidden rounded-[14px] border border-[var(--color-chalk)] bg-gradient-warm transition hover:shadow-hairline"
      >
        {selected ? (
          <div className="flex flex-col items-center gap-2 text-[var(--color-obsidian)]">
            <span className="text-[15px] font-medium">{selected.original_filename}</span>
            <span className="text-[12px] text-[var(--color-gravel)]">
              {selected.duration_s != null ? formatSeconds(selected.duration_s) : "—"} ·{" "}
              {selected.shot_count ?? 0} shots
            </span>
            <span className="mt-2 rounded-full bg-[var(--color-obsidian)] px-3 py-1 text-[12px] text-white">
              {t("pgkit.video_picker.change")}
            </span>
          </div>
        ) : (
          <span className="inline-flex items-center gap-2 rounded-md bg-[var(--color-obsidian)] px-3 py-1.5 text-[13px] text-white">
            <VideoIcon size={13} />
            {loading ? t("actions.loading") : resolvedEmptyLabel}
          </span>
        )}
      </button>
      <VideoPickerModal
        open={open}
        onClose={() => setOpen(false)}
        videos={videos}
        loading={loading}
        error={error}
        selectedId={selectedId}
        onSelect={(v) => {
          onSelect(v);
          setOpen(false);
        }}
      />
    </>
  );
}

/**
 * Standalone "Select a video" modal — usable when the parent controls its own
 * trigger affordance (e.g. a header button rather than the gradient card).
 * Auto-refreshes the list on open so freshly uploaded assets appear without
 * a page reload, and offers a direct path to the Assets page when empty.
 */
export function VideoPickerModal({
  open,
  onClose,
  videos,
  loading,
  error,
  selectedId,
  onSelect,
  onRefresh,
}: {
  open: boolean;
  onClose: () => void;
  videos: VideoSummary[];
  loading: boolean;
  error: string | null;
  selectedId?: string;
  onSelect: (v: VideoSummary) => void;
  onRefresh?: () => void;
}) {
  const { t } = useTranslation();

  useEffect(() => {
    if (open) onRefresh?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;
  const isEmpty = !loading && !error && videos.length === 0;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-6" onClick={onClose}>
      <div
        className="flex max-h-[80vh] w-full max-w-[640px] flex-col overflow-hidden rounded-[20px] bg-white shadow-[0_24px_64px_0_rgba(28,29,27,0.35)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <h2 className="text-[15px] font-semibold text-neutral-900">{t("pgkit.video_picker.modal_title")}</h2>
            <span className="rounded-full bg-neutral-100 px-2 py-0.5 font-mono text-[10px] text-neutral-600">
              {loading ? "…" : t("pgkit.video_picker.ready_count", { count: videos.length })}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => onRefresh?.()}
              disabled={loading}
              className="grid h-8 w-8 place-items-center rounded-[10px] text-neutral-700 hover:bg-neutral-100 disabled:text-neutral-400"
              title={t("pgkit.video_picker.refresh")}
              aria-label={t("pgkit.video_picker.refresh_list")}
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="grid h-8 w-8 place-items-center rounded-[10px] text-neutral-700 hover:bg-neutral-100"
              aria-label={t("actions.close")}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {error && (
            <div className="m-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-[13px] text-rose-700">
              {error}
            </div>
          )}

          {isEmpty && (
            <div className="m-4 flex flex-col items-center gap-3 rounded-[14px] border border-dashed border-neutral-300 bg-neutral-50 p-8 text-center">
              <UploadCloud size={28} className="text-neutral-400" />
              <p className="text-[14px] font-medium text-neutral-900">{t("pgkit.video_picker.empty_title")}</p>
              <p className="max-w-[360px] text-[12px] text-neutral-600">
                {t("pgkit.video_picker.empty_desc")}
              </p>
              <Link
                to="/assets"
                onClick={onClose}
                className="mt-2 inline-flex items-center gap-2 rounded-full bg-neutral-900 px-4 py-2 text-[13px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-700 active:scale-[0.97]"
              >
                {t("pgkit.video_picker.open_assets")} <span aria-hidden>→</span>
              </Link>
            </div>
          )}

          {loading && videos.length === 0 && !error && (
            <div className="space-y-2 p-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-lg bg-neutral-100" />
              ))}
            </div>
          )}

          {videos.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => onSelect(v)}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-lg px-4 py-2.5 text-left text-[13px] transition hover:bg-neutral-100",
                selectedId === v.id && "bg-neutral-100",
              )}
            >
              <span className="flex min-w-0 flex-1 items-center gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-neutral-100 text-neutral-500">
                  <VideoIcon size={14} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-neutral-900">{v.original_filename}</span>
                  <span className="font-mono text-[11px] text-neutral-500">
                    {v.duration_s != null ? formatSeconds(v.duration_s) : "—"} · {v.shot_count ?? 0} shots
                  </span>
                </span>
              </span>
              {selectedId === v.id && <Check size={14} className="text-neutral-900" />}
            </button>
          ))}
        </div>

        {!isEmpty && (
          <div className="border-t border-neutral-200 px-6 py-3 text-right">
            <Link
              to="/assets"
              onClick={onClose}
              className="inline-flex items-center gap-1 text-[12px] text-neutral-600 hover:text-neutral-900"
            >
              {t("pgkit.video_picker.manage_assets")} <span aria-hidden>→</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

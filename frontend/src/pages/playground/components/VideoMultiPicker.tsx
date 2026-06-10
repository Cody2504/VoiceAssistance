import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, RefreshCw, Video as VideoIcon, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { listIndexVideos, type IndexVideoEntry } from "@/apis/indexes.api";
import { cn, formatSeconds } from "@/lib/utils";

interface Props {
  indexId: string;
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  emptyLabel?: string;
}

/**
 * Multi-select picker for videos inside a given Index. Used by the chat scope bar
 * when the user wants to ask against a SUBSET of an Index's videos rather than the
 * whole thing. Selection is controlled by the parent (selectedIds + onChange) so
 * the chat state stays the single source of truth.
 */
export function VideoMultiPicker({
  indexId,
  selectedIds,
  onChange,
  emptyLabel,
}: Props) {
  const { t } = useTranslation();
  const resolvedEmptyLabel = emptyLabel ?? t("pgkit.video_multi_picker.default_label");
  const [open, setOpen] = useState(false);
  const [videos, setVideos] = useState<IndexVideoEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!indexId) return;
    setLoading(true);
    listIndexVideos(indexId)
      .then(setVideos)
      .catch(() => setVideos([]))
      .finally(() => setLoading(false));
  }, [indexId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  const total = videos.length;
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const triggerLabel = selectedIds.length === 0
    ? resolvedEmptyLabel
    : t("pgkit.video_multi_picker.selected_of", { selected: selectedIds.length, total });

  const toggle = (vid: string) => {
    const next = new Set(selectedSet);
    if (next.has(vid)) next.delete(vid);
    else next.add(vid);
    onChange(Array.from(next));
  };

  const selectAll = () => onChange(videos.map((v) => v.video_id));
  const clear = () => onChange([]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-[var(--color-chalk)] bg-white px-3 text-[13px] transition hover:border-[var(--color-gravel)]"
      >
        <span className="flex min-w-0 items-center gap-2">
          <VideoIcon size={14} className="shrink-0 text-[var(--color-gravel)]" />
          <span className="truncate text-[var(--color-obsidian)]">{triggerLabel}</span>
        </span>
        <span className="text-[11px] text-[var(--color-gravel)]">edit</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-6" onClick={() => setOpen(false)}>
          <div
            className="flex max-h-[80vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
              <div className="flex items-center gap-2">
                <h2 className="text-[15px] font-semibold text-neutral-900">{t("pgkit.video_multi_picker.modal_title")}</h2>
                <span className="rounded-full bg-neutral-100 px-2 py-0.5 font-mono text-[10px] text-neutral-600">
                  {loading ? "…" : `${selectedIds.length} / ${total}`}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading}
                  className="grid h-8 w-8 place-items-center rounded-[10px] text-neutral-700 hover:bg-neutral-100 disabled:text-neutral-400"
                  title={t("pgkit.video_picker.refresh")}
                >
                  <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="grid h-8 w-8 place-items-center rounded-[10px] text-neutral-700 hover:bg-neutral-100"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between px-6 py-2">
              <button
                onClick={selectAll}
                className="text-[12px] text-[var(--color-obsidian)] hover:underline"
              >
                {t("pgkit.video_multi_picker.select_all")}
              </button>
              <button
                onClick={clear}
                className="text-[12px] text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]"
              >
                {t("actions.clear")}
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {!loading && total === 0 && (
                <div className="m-4 rounded-[14px] border border-dashed border-neutral-300 bg-neutral-50 p-6 text-center text-[13px] text-neutral-600">
                  {t("pgkit.video_multi_picker.no_videos")}
                </div>
              )}
              {videos.map((v) => {
                const checked = selectedSet.has(v.video_id);
                return (
                  <button
                    key={v.video_id}
                    type="button"
                    onClick={() => toggle(v.video_id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 rounded-lg px-4 py-2.5 text-left text-[13px] transition hover:bg-neutral-100",
                      checked && "bg-neutral-100",
                    )}
                  >
                    <span className="flex min-w-0 flex-1 items-center gap-3">
                      <span
                        className={cn(
                          "grid h-4 w-4 shrink-0 place-items-center rounded border",
                          checked
                            ? "border-[var(--color-obsidian)] bg-[var(--color-obsidian)] text-white"
                            : "border-[var(--color-chalk)] bg-white",
                        )}
                      >
                        {checked && <Check size={11} />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-neutral-900">{v.original_filename}</span>
                        <span className="font-mono text-[11px] text-neutral-500">
                          #{v.position} · {v.duration_s != null ? formatSeconds(v.duration_s) : "—"} ·{" "}
                          {v.status}
                        </span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="border-t border-neutral-200 px-6 py-3 text-right">
              <button
                onClick={() => setOpen(false)}
                className="rounded-full bg-[var(--color-obsidian)] px-4 py-1.5 text-[13px] text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]"
              >
                {t("pgkit.video_multi_picker.done")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

import { useMemo } from "react";
import { Filter, RotateCcw, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { SegmentDefinition, SegmentRunResponse } from "@/apis/videos.api";

export interface SegmentRunHistoryEntry {
  /** Stable key for this run (timestamp ms). */
  id: number;
  /** ISO timestamp for display. */
  created_at: string;
  /** Source video id (lets us refilter / reload). */
  video_id: string;
  /** Original filename for the card title; preset id fallback if blank. */
  title: string;
  /** Definitions that were submitted. */
  definitions: SegmentDefinition[];
  /** Result payload — replayable without hitting the backend again. */
  result: SegmentRunResponse;
}

const KEY = "tl_jockey_segment_history";

export function loadHistory(): SegmentRunHistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as SegmentRunHistoryEntry[];
  } catch {
    return [];
  }
}

export function saveHistory(entries: SegmentRunHistoryEntry[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries.slice(0, 30)));
  } catch {
    /* ignore quota errors */
  }
}

export function appendHistory(entry: SegmentRunHistoryEntry) {
  const next = [entry, ...loadHistory()];
  saveHistory(next);
  return next;
}

interface Props {
  open: boolean;
  onClose: () => void;
  entries: SegmentRunHistoryEntry[];
  filter: string;
  onFilterChange: (v: string) => void;
  onPick: (entry: SegmentRunHistoryEntry) => void;
  onClear: () => void;
}

function formatStamp(iso: string) {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return iso;
  }
}

export function HistoryPanel({
  open,
  onClose,
  entries,
  filter,
  onFilterChange,
  onPick,
  onClear,
}: Props) {
  const { t } = useTranslation();
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) => e.video_id.toLowerCase().includes(q) || e.title.toLowerCase().includes(q),
    );
  }, [entries, filter]);

  if (!open) return null;
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[460px] max-w-[90vw] flex-col overflow-hidden bg-white pt-5 shadow-[0_0_24px_0_rgba(28,29,27,0.25)]">
        <div className="mb-5 flex items-center justify-between px-8">
          <h2 className="text-[22px] font-semibold text-neutral-900">{t("pgkit.history.title")}</h2>
          <button
            type="button"
            onClick={onClose}
            className="grid h-10 w-10 place-items-center rounded-[12px] text-neutral-900 hover:bg-neutral-100"
            aria-label={t("pgkit.history.close")}
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex items-center gap-x-3 px-8">
          <div className="relative flex h-10 w-[280px] items-center gap-1 rounded-lg border border-neutral-300 px-4 focus-within:border-neutral-800">
            <Filter size={18} className="shrink-0 text-neutral-500" />
            <input
              value={filter}
              onChange={(e) => onFilterChange(e.target.value)}
              placeholder={t("pgkit.history.filter_placeholder")}
              className="h-full w-full bg-transparent text-[13px] outline-none placeholder:text-neutral-500"
            />
          </div>
          <button
            type="button"
            onClick={onClear}
            disabled={entries.length === 0}
            className="ml-auto grid h-8 w-8 place-items-center rounded-[10px] text-neutral-900 hover:bg-neutral-100 disabled:text-neutral-400"
            aria-label={t("pgkit.history.clear")}
            title={t("pgkit.history.clear")}
          >
            <RotateCcw size={18} />
          </button>
        </div>

        <div className="mt-2 flex px-8">
          <span className="whitespace-nowrap text-[13px] text-neutral-600">
            {t(filtered.length === 1 ? "pgkit.history.task_count_one" : "pgkit.history.task_count_other", { count: filtered.length })}
          </span>
        </div>

        <div className="mt-3 flex flex-1 min-h-0 flex-col gap-y-3 overflow-y-auto px-8 pb-8">
          {filtered.length === 0 && (
            <div className="rounded-2xl border border-dashed border-neutral-300 p-6 text-center text-[13px] text-neutral-500">
              {entries.length === 0
                ? t("pgkit.history.empty_no_runs")
                : t("pgkit.history.empty_no_match")}
            </div>
          )}
          {filtered.map((entry) => {
            const trackCount = entry.result.tracks.length;
            const segCount = entry.result.tracks.reduce(
              (s, track) => s + track.segments.length,
              0,
            );
            return (
              <button
                key={entry.id}
                type="button"
                onClick={() => onPick(entry)}
                className="flex w-full items-center gap-2 rounded-2xl border border-neutral-300 bg-neutral-200 p-5 text-left transition hover:border-neutral-500"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-y-2">
                  <div className="flex items-center justify-between gap-x-2">
                    <span className="truncate text-[15px] text-neutral-900">{entry.title}</span>
                    <span className="shrink-0 rounded-md border border-green-700 bg-green-900 px-1.5 py-0.5 font-mono text-[11px] capitalize text-green-100">
                      {t("pgkit.history.status_ready")}
                    </span>
                  </div>
                  <div className="flex items-center gap-x-3 text-[12px] text-neutral-700">
                    <span className="shrink-0">{formatStamp(entry.created_at)}</span>
                    <span className="h-3.5 w-px bg-neutral-400" aria-hidden />
                    <span className="font-mono text-[11px] text-neutral-500">
                      {t(trackCount === 1 ? "pgkit.history.track_seg" : "pgkit.history.tracks_seg", { tracks: trackCount, segs: segCount })}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </aside>
    </>
  );
}

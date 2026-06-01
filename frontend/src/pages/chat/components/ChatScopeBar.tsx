import { useEffect, useState } from "react";

import { listIndexes, type IndexSummary } from "@/apis/indexes.api";
import { cn } from "@/lib/utils";
import { VideoMultiPicker } from "@/pages/playground/components/VideoMultiPicker";

export type ChatScopeMode = "single" | "subset" | "whole";

export interface ChatScopeValue {
  mode: ChatScopeMode;
  indexId?: string;
  indexTitle?: string;
  videoIds: string[];
}

interface Props {
  value: ChatScopeValue;
  onChange: (v: ChatScopeValue) => void;
}

const MODES: { id: ChatScopeMode; label: string; hint: string }[] = [
  { id: "single", label: "Single video", hint: "Ask about one video — uses drag-attached video(s) below." },
  { id: "subset", label: "Selected videos", hint: "Pick an Index, then choose which of its videos to include." },
  { id: "whole", label: "Whole index", hint: "Search every video in an Index — best for cross-video questions." },
];

/**
 * Three-mode scope selector for the chat. Controls what gets sent alongside the
 * user's message:
 *  - "single" → no index_id; the existing drag-attached videos in the composer drive scope.
 *  - "subset" → index_id + a hand-picked subset of its videos.
 *  - "whole"  → index_id only (the backend resolves all videos in the index).
 */
export function ChatScopeBar({ value, onChange }: Props) {
  // When mode changes, reset id/video_ids to keep the state consistent with the mode.
  const setMode = (mode: ChatScopeMode) => {
    if (mode === "single") onChange({ mode, indexId: undefined, indexTitle: undefined, videoIds: [] });
    else if (mode === "whole") onChange({ mode, indexId: value.indexId, indexTitle: value.indexTitle, videoIds: [] });
    else onChange({ mode, indexId: value.indexId, indexTitle: value.indexTitle, videoIds: value.videoIds });
  };

  const activeHint = MODES.find((m) => m.id === value.mode)?.hint ?? "";

  return (
    <div className="mb-3 rounded-xl border border-neutral-200 bg-neutral-50/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-2 text-[11px] uppercase tracking-wide text-neutral-500">Scope</span>
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            className={cn(
              "rounded-full px-3 py-1 text-[12px] transition",
              value.mode === m.id
                ? "bg-[var(--color-obsidian)] text-white"
                : "bg-white text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]",
            )}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-neutral-500">{activeHint}</p>

      {value.mode !== "single" && (
        <div className="mt-3 space-y-2">
          <InlineIndexPicker
            selectedIndexId={value.indexId}
            onSelect={(idx) =>
              onChange({ ...value, indexId: idx.id, indexTitle: idx.title, videoIds: value.mode === "whole" ? [] : value.videoIds })
            }
          />
          {value.mode === "subset" && value.indexId && (
            <VideoMultiPicker
              indexId={value.indexId}
              selectedIds={value.videoIds}
              onChange={(ids) => onChange({ ...value, videoIds: ids })}
            />
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Slim inline index picker — a pill dropdown of the user's indexes. Lives only
 * inside the chat scope bar; for full-page index selection use the upstream
 * `IndexPicker` component which renders a large gradient card.
 */
function InlineIndexPicker({
  selectedIndexId,
  onSelect,
}: {
  selectedIndexId?: string;
  onSelect: (idx: { id: string; title: string }) => void;
}) {
  const [open, setOpen] = useState(false);
  const [indexes, setIndexes] = useState<IndexSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    listIndexes()
      .then(setIndexes)
      .catch(() => setIndexes([]))
      .finally(() => setLoading(false));
  }, []);

  const selected = indexes.find((i) => i.id === selectedIndexId) ?? null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-[var(--color-chalk)] bg-white px-3 text-[13px] text-[var(--color-obsidian)] transition hover:border-[var(--color-gravel)]"
      >
        <span className="truncate">
          {selected ? selected.title || "Untitled Index" : loading ? "Loading…" : "Pick an index"}
        </span>
        <span className="text-[11px] text-[var(--color-gravel)]">
          {selected ? `${selected.video_count} videos` : "select"}
        </span>
      </button>
      {open && (
        <div
          className="absolute left-0 right-0 top-10 z-40 max-h-[280px] overflow-y-auto rounded-md border border-[var(--color-chalk)] bg-white p-1 shadow-hairline"
        >
          {indexes.length === 0 && !loading && (
            <div className="px-3 py-4 text-center text-[12px] text-[var(--color-gravel)]">
              No indexes yet.{" "}
              <a href="/indexes" className="text-[var(--color-obsidian)] underline">
                Create one
              </a>
              .
            </div>
          )}
          {indexes.map((i) => (
            <button
              key={i.id}
              type="button"
              onClick={() => {
                onSelect({ id: i.id, title: i.title || "Untitled Index" });
                setOpen(false);
              }}
              className={cn(
                "block w-full rounded px-3 py-1.5 text-left text-[12px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                selectedIndexId === i.id && "bg-[var(--color-powder)] font-medium",
              )}
            >
              <span className="block truncate">{i.title || "Untitled Index"}</span>
              <span className="font-mono text-[10px] text-[var(--color-gravel)]">
                {i.video_count} video{i.video_count === 1 ? "" : "s"}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

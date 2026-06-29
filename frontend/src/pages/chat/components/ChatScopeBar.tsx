import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { listIndexes, type IndexSummary } from "@/apis/indexes.api";
import { cn } from "@/lib/utils";

export type ChatScopeMode = "single" | "whole";

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

interface ModeItem {
  id: ChatScopeMode;
  labelKey: string;
  hintKey: string;
}

const MODES: ModeItem[] = [
  { id: "single", labelKey: "chat.scope.mode_single_label", hintKey: "chat.scope.mode_single_hint" },
  { id: "whole",  labelKey: "chat.scope.mode_whole_label",  hintKey: "chat.scope.mode_whole_hint"  },
];

/**
 * Two-mode scope selector for the chat. Controls what gets sent alongside the
 * user's message:
 *  - "single" (General) → no index_id; ask about whatever video(s) you drag into the composer.
 *  - "whole" (Selected index) → index_id only; ask across a chosen index (knowledge graph).
 */
export function ChatScopeBar({ value, onChange }: Props) {
  const { t } = useTranslation();

  // When mode changes, reset id/video_ids to keep the state consistent with the mode.
  const setMode = (mode: ChatScopeMode) => {
    if (mode === "single") onChange({ mode, indexId: undefined, indexTitle: undefined, videoIds: [] });
    else onChange({ mode, indexId: value.indexId, indexTitle: value.indexTitle, videoIds: [] });
  };

  const activeHintKey = MODES.find((m) => m.id === value.mode)?.hintKey ?? "";

  return (
    <div className="mb-3 rounded-xl border border-neutral-200 bg-neutral-50/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-2 text-[11px] uppercase tracking-wide text-neutral-500">{t("chat.scope.label")}</span>
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
            {t(m.labelKey)}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-neutral-500">{activeHintKey ? t(activeHintKey) : ""}</p>

      {value.mode !== "single" && (
        <div className="mt-3 space-y-2">
          <InlineIndexPicker
            selectedIndexId={value.indexId}
            onSelect={(idx) => onChange({ ...value, indexId: idx.id, indexTitle: idx.title, videoIds: [] })}
          />
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
  const { t } = useTranslation();
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
          {selected
            ? selected.title || t("chat.index_picker.untitled")
            : loading
              ? t("actions.loading")
              : t("chat.index_picker.placeholder")}
        </span>
        <span className="text-[11px] text-[var(--color-gravel)]">
          {selected
            ? t(selected.video_count === 1 ? "chat.index_picker.video_count_one" : "chat.index_picker.video_count_other", { count: selected.video_count })
            : t("chat.index_picker.select_hint")}
        </span>
      </button>
      {open && (
        <div
          className="absolute left-0 right-0 top-10 z-40 max-h-[280px] overflow-y-auto rounded-md border border-[var(--color-chalk)] bg-white p-1 shadow-hairline"
        >
          {indexes.length === 0 && !loading && (
            <div className="px-3 py-4 text-center text-[12px] text-[var(--color-gravel)]">
              {t("chat.index_picker.empty")}{" "}
              <a href="/indexes" className="text-[var(--color-obsidian)] underline">
                {t("chat.index_picker.empty_create")}
              </a>
              .
            </div>
          )}
          {indexes.map((i) => (
            <button
              key={i.id}
              type="button"
              onClick={() => {
                onSelect({ id: i.id, title: i.title || t("chat.index_picker.untitled") });
                setOpen(false);
              }}
              className={cn(
                "block w-full rounded px-3 py-1.5 text-left text-[12px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                selectedIndexId === i.id && "bg-[var(--color-powder)] font-medium",
              )}
            >
              <span className="block truncate">{i.title || t("chat.index_picker.untitled")}</span>
              <span className="font-mono text-[10px] text-[var(--color-gravel)]">
                {t(i.video_count === 1 ? "chat.index_picker.video_count_one" : "chat.index_picker.video_count_other", { count: i.video_count })}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

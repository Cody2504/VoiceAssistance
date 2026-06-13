import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, ChevronDown, Copy, Sparkles, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { IndexVideoEntry } from "@/apis/indexes.api";
import { getStreamUrl } from "@/apis/videos.api";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  items: IndexVideoEntry[];
  /** Position in `items` of the video being previewed. */
  current: number;
  onNavigate: (next: number) => void;
  onClose: () => void;
  onAnalyze: (videoId: string) => void;
}

/** TwelveLabs-style preview dialog: title, Copy IDs dropdown, player,
 *  prev/next pager + Analyze. */
export function IndexVideoPreviewModal({ open, items, current, onNavigate, onClose, onAnalyze }: Props) {
  const { t } = useTranslation();
  const entry = open ? items[current] : undefined;
  const [url, setUrl] = useState<string | null>(null);
  const [idsOpen, setIdsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setUrl(null);
    setIdsOpen(false);
    setCopied(false);
    if (!entry) return;
    let alive = true;
    getStreamUrl(entry.video_id)
      .then((u) => {
        if (alive) setUrl(u);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry?.video_id]);

  if (!open || !entry) return null;

  const copyId = async () => {
    try {
      await navigator.clipboard.writeText(entry.video_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (http origin) — ignore */
    }
  };

  return (
    <div className="overlay-in fixed inset-0 z-50 grid place-items-center bg-black/45 p-6" onClick={onClose}>
      <div
        className="modal-pop w-full max-w-[576px] overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 p-5 pb-3">
          <h6 className="min-w-0 break-all text-[15px] font-medium leading-snug text-[var(--color-obsidian)]">
            {entry.original_filename}
          </h6>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--color-gravel)] transition hover:bg-[var(--color-powder)]"
          >
            <X size={16} />
          </button>
        </div>

        <div className="relative px-5 pb-3">
          <button
            onClick={() => setIdsOpen((o) => !o)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-chalk)] px-2.5 py-1 text-[12px] text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
          >
            <Copy size={12} />
            {t("console.index_preview.copy_ids")}
            <ChevronDown size={12} />
          </button>
          {idsOpen && (
            <div className="absolute left-5 top-9 z-10 w-44 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
              <button
                onClick={copyId}
                className="flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-[12px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
              >
                {copied ? t("console.index_preview.copied") : t("console.index_preview.video_id")}
                {copied && <Check size={12} className="text-emerald-600" />}
              </button>
            </div>
          )}
        </div>

        {url ? (
          <video src={url} controls autoPlay className="aspect-video w-full bg-black" />
        ) : (
          <div className="grid aspect-video w-full place-items-center bg-neutral-950 text-[13px] text-neutral-400">
            {t("console.preview.loading")}
          </div>
        )}

        <div className="flex items-center justify-between p-4">
          <button
            onClick={() => onAnalyze(entry.video_id)}
            className="inline-flex items-center gap-1 rounded-[8.4px] px-2.5 py-1.5 text-[12px] text-[var(--color-obsidian)] shadow-[0px_0px_0px_1px_var(--color-chalk)_inset] transition-all hover:rounded-[11.2px] hover:bg-black/5"
          >
            {t("console.index_preview.analyze")}
            <Sparkles size={13} />
          </button>
          <div className="flex items-center gap-1.5">
            <button
              aria-label={t("console.index_preview.prev")}
              disabled={current <= 0}
              onClick={() => onNavigate(current - 1)}
              className={cn(
                "grid h-8 w-8 place-items-center rounded-md border border-[var(--color-chalk)] transition",
                current <= 0 ? "opacity-40" : "hover:bg-[var(--color-powder)]",
              )}
            >
              <ArrowLeft size={14} />
            </button>
            <button
              aria-label={t("console.index_preview.next")}
              disabled={current >= items.length - 1}
              onClick={() => onNavigate(current + 1)}
              className={cn(
                "grid h-8 w-8 place-items-center rounded-md border border-[var(--color-chalk)] transition",
                current >= items.length - 1 ? "opacity-40" : "hover:bg-[var(--color-powder)]",
              )}
            >
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

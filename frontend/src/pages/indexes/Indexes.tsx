import { useCallback, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { Info, ArrowRight, Search as SearchIcon, ChevronDown, X, Play, MoreVertical } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PillButton } from "@/components/ui/PillButton";
import { createIndex, deleteIndex, type IndexSummary } from "@/apis/indexes.api";
import { useVideosQuery, useIndexesQuery, qk } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

type SortKey = "recent" | "name" | "duration";

interface IndexCardData {
  id: string;
  title: string;
  videos: number;
  durationLabel: string;
  createdAt: string;
  variant: "default" | "real-a" | "real-b" | "real-c" | "real-d" | "real-e";
  href?: string;
  sortableTime: number;
  isReal: boolean;
}

function fmtDuration(totalSec: number): string {
  if (totalSec < 60) return `${Math.round(totalSec)}s`;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function IndexCard({ data, onDelete }: { data: IndexCardData; onDelete?: (id: string) => void }) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const tile = {
    default: "bg-gradient-warm",
    "real-a": "bg-gradient-to-br from-amber-100 via-orange-100 to-emerald-100",
    "real-b": "bg-gradient-to-br from-rose-100 via-pink-100 to-violet-100",
    "real-c": "bg-gradient-to-br from-sky-100 via-cyan-100 to-emerald-100",
    "real-d": "bg-gradient-to-br from-amber-100 via-rose-100 to-sky-100",
    "real-e": "bg-gradient-to-br from-lime-100 via-emerald-100 to-orange-100",
  }[data.variant];

  const body = (
    <div className="group cursor-pointer">
      <div
        className={cn(
          "relative h-[180px] overflow-hidden border border-[var(--color-chalk)] transition-all duration-200 ease-out",
          "rounded-[16px] group-hover:rounded-[22px] group-hover:shadow-hairline",
          tile,
        )}
      >
        <div className="absolute bottom-3 left-3 inline-flex items-center gap-2 rounded-md bg-black/55 px-2 py-1 text-[11px] text-white">
          <Play size={11} fill="currentColor" />
          {data.videos === 1
            ? t("console.indexes.video_count_one", { count: data.videos })
            : t("console.indexes.video_count_other", { count: data.videos })}{" "}
          ({data.durationLabel})
        </div>
      </div>
      <div className="mt-3 flex items-start justify-between">
        <div>
          <h4 className="text-[15px] font-medium text-[var(--color-obsidian)]">{data.title}</h4>
          <p className="mt-0.5 text-[12px] text-[var(--color-gravel)]">{data.createdAt}</p>
        </div>
        {data.isReal && onDelete && (
          <div className="relative">
            <button
              className="opacity-0 transition group-hover:opacity-100"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setMenuOpen((o) => !o);
              }}
            >
              <MoreVertical size={16} className="text-[var(--color-gravel)]" />
            </button>
            {menuOpen && (
              <div
                className="absolute right-0 top-6 z-10 w-32 rounded-md border border-[var(--color-chalk)] bg-white p-1 shadow-hairline"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
              >
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    if (confirm(t("console.indexes.delete_confirm", { title: data.title }))) onDelete(data.id);
                  }}
                  className="block w-full rounded px-2 py-1 text-left text-[12px] text-rose-600 hover:bg-rose-50"
                >
                  {t("console.indexes.delete_label")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return data.href ? (
    <Link to={data.href}>{body}</Link>
  ) : (
    body
  );
}

function CreateIndexModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (summary: IndexSummary) => void;
}) {
  const { t } = useTranslation();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    if (!title.trim()) {
      setError(t("console.create_index_modal.error_title_required"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await createIndex({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      onCreated(created);
      setTitle("");
      setDescription("");
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("console.create_index_modal.error_create_failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-6" onClick={onClose}>
      <div
        className="w-full max-w-[440px] rounded-2xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[var(--color-obsidian)]">
            {t("console.create_index_modal.title")}
          </h2>
          <button onClick={onClose} className="rounded p-1 text-[var(--color-gravel)] hover:bg-[var(--color-powder)]">
            <X size={16} />
          </button>
        </div>
        <p className="mb-4 text-[12px] text-[var(--color-gravel)]">
          {t("console.create_index_modal.description")}
        </p>
        <label className="mb-3 block">
          <span className="mb-1 block text-[12px] font-medium text-[var(--color-obsidian)]">
            {t("console.create_index_modal.label_title")}
          </span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("console.create_index_modal.placeholder_title")}
            className="h-9 w-full rounded-md border border-[var(--color-chalk)] bg-white px-3 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--color-obsidian)]/10"
            autoFocus
          />
        </label>
        <label className="mb-4 block">
          <span className="mb-1 block text-[12px] font-medium text-[var(--color-obsidian)]">
            {t("console.create_index_modal.label_description")}{" "}
            <span className="text-[var(--color-gravel)]">{t("console.create_index_modal.optional")}</span>
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-[var(--color-chalk)] bg-white px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[var(--color-obsidian)]/10"
          />
        </label>
        {error && <p className="mb-3 text-[12px] text-rose-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-full px-4 py-1.5 text-[13px] text-[var(--color-gravel)] hover:bg-[var(--color-powder)]"
          >
            {t("actions.cancel")}
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="rounded-full bg-[var(--color-obsidian)] px-4 py-1.5 text-[13px] text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97] disabled:opacity-50 disabled:active:scale-100"
          >
            {submitting ? t("console.create_index_modal.btn_creating") : t("console.create_index_modal.btn_create")}
          </button>
        </div>
      </div>
    </div>
  );
}

const VARIANT_ROTATION: IndexCardData["variant"][] = [
  "real-c", "real-a", "real-d", "real-b", "real-e",
];

export default function Indexes() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: videos = [] } = useVideosQuery();
  const { data: indexes = [] } = useIndexesQuery();
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("recent");
  const [bannerVisible, setBannerVisible] = useState(true);
  const [sortOpen, setSortOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const reloadIndexes = useCallback(() => {
    qc.invalidateQueries({ queryKey: qk.indexes(user?.id) });
  }, [qc, user?.id]);

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteIndex(id);
        reloadIndexes();
      } catch {
        // best-effort UX; a toast layer would belong here
      }
    },
    [reloadIndexes],
  );

  const sortLabels: Record<SortKey, string> = {
    recent: t("console.indexes.sort_recent"),
    name: t("console.indexes.sort_name"),
    duration: t("console.indexes.sort_duration"),
  };

  const cards: IndexCardData[] = useMemo(() => {
    const totalDuration = videos.reduce((s, v) => s + (v.duration_s ?? 0), 0);
    const defaultCard: IndexCardData = {
      id: "default",
      title: t("console.indexes.default_title"),
      videos: videos.length,
      durationLabel: videos.length ? fmtDuration(totalDuration) : "0s",
      createdAt: t("console.indexes.created_on", {
        date: new Date().toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" }),
      }),
      variant: "default",
      href: "/playground/library",
      sortableTime: Date.now(),
      isReal: false,
    };
    const realCards: IndexCardData[] = indexes.map((idx, n) => ({
      id: idx.id,
      title: idx.title || t("console.indexes.untitled"),
      videos: idx.video_count,
      durationLabel: idx.total_duration_s ? fmtDuration(idx.total_duration_s) : "0s",
      createdAt: t("console.indexes.created_on", {
        date: new Date(idx.created_at).toLocaleDateString("en-US", {
          month: "short",
          day: "2-digit",
          year: "numeric",
        }),
      }),
      variant: VARIANT_ROTATION[n % VARIANT_ROTATION.length],
      href: `/indexes/${idx.id}`,
      sortableTime: Date.parse(idx.created_at),
      isReal: true,
    }));

    const all = [defaultCard, ...realCards];
    const filtered = filter
      ? all.filter((c) => c.title.toLowerCase().includes(filter.toLowerCase()))
      : all;

    const sorted = [...filtered].sort((a, b) => {
      if (sortKey === "name") return a.title.localeCompare(b.title);
      if (sortKey === "duration") return b.videos - a.videos;
      return b.sortableTime - a.sortableTime;
    });
    return sorted;
  }, [videos, indexes, filter, sortKey, t]);

  const sortLabel = sortLabels[sortKey];

  return (
    <div className="mx-auto max-w-[1180px] px-8 py-6">
      <div className="mb-6 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-[32px] font-light tracking-[-0.64px] text-[var(--color-obsidian)]">
            {t("console.indexes.title")}
          </h1>
          <Info size={14} className="text-[var(--color-slate)]" />
        </div>
        <PillButton
          variant="ghost"
          rightIcon={<ArrowRight size={14} />}
          onClick={() => setCreateOpen(true)}
        >
          {t("console.indexes.create_btn")}
        </PillButton>
      </div>

      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="relative max-w-[320px] flex-1">
          <SearchIcon
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-slate)]"
          />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("console.indexes.filter_placeholder")}
            className="h-9 w-full rounded-full border border-[var(--color-chalk)] bg-white pl-9 pr-3 text-[13px] text-[var(--color-obsidian)] placeholder:text-[var(--color-slate)] focus:outline-none focus:ring-2 focus:ring-[var(--color-obsidian)]/10"
          />
        </div>

        <div className="relative">
          <button
            onClick={() => setSortOpen((o) => !o)}
            className="inline-flex h-9 items-center gap-2 rounded-full border border-transparent px-3 text-[13px] text-[var(--color-gravel)] hover:bg-[var(--color-powder)]"
          >
            <span className="text-[var(--color-slate)]">{t("console.indexes.sort_by")}</span>
            <span className="text-[var(--color-obsidian)]">{sortLabel}</span>
            <ChevronDown size={13} />
          </button>
          {sortOpen && (
            <div className="absolute right-0 top-10 z-10 w-44 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
              {(["recent", "name", "duration"] as SortKey[]).map((k) => (
                <button
                  key={k}
                  onClick={() => {
                    setSortKey(k);
                    setSortOpen(false);
                  }}
                  className={cn(
                    "block w-full rounded-md px-3 py-1.5 text-left text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                    sortKey === k && "bg-[var(--color-powder)] font-medium",
                  )}
                >
                  {sortLabels[k]}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {bannerVisible && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-[#bce5b6] bg-[#dff5d8] px-4 py-2.5 text-[12px] text-[#1e5a23]">
          <Info size={14} className="shrink-0" />
          {t("console.indexes.free_plan_banner")}
          <button
            onClick={() => setBannerVisible(false)}
            className="ml-auto text-[#1e5a23]/60 hover:text-[#1e5a23]"
          >
            <X size={13} />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-x-6 gap-y-8 pb-12 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <IndexCard key={c.id} data={c} onDelete={c.isReal ? handleDelete : undefined} />
        ))}
      </div>

      <CreateIndexModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => reloadIndexes()}
      />

      <div className="flex items-center justify-center gap-1 pb-10 text-[13px] text-[var(--color-gravel)]">
        <button className="grid h-7 w-7 place-items-center rounded-md border border-[var(--color-chalk)] bg-white hover:bg-[var(--color-powder)]">‹</button>
        <span className="grid h-7 w-7 place-items-center rounded-md border border-[var(--color-chalk)] bg-[var(--color-powder)] text-[var(--color-obsidian)]">
          1
        </span>
        <button className="grid h-7 w-7 place-items-center rounded-md border border-[var(--color-chalk)] bg-white hover:bg-[var(--color-powder)]">›</button>
      </div>
    </div>
  );
}

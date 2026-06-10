import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Info,
  Upload,
  Search as SearchIcon,
  ChevronDown,
  LayoutGrid,
  List as ListIcon,
  Film,
  Image as ImageIcon,
  Music2,
  Play,
  Loader2,
  CheckCircle2,
  Clock,
  AlertCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { PillButton } from "@/components/ui/PillButton";
import { uploadVideo, getPosterUrl, type VideoSummary } from "@/apis/videos.api";
import { useVideosQuery, useS3ObjectsQuery, qk } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

type Filter = "all" | "video" | "image" | "audio";
type ViewMode = "grid" | "list";

interface AssetRow {
  id: string;
  name: string;
  kind: "video" | "image" | "audio";
  durationLabel?: string;
  thumbUrl?: string;
  size?: string;
  modified?: string;
  status?: VideoSummary["status"];
}

/** Indexing status pill. `queued`/`processing` = the worker is still running the
 *  IV2/TransNet/SG-DETR pipeline; `ready` = searchable; `error` = ingest failed.
 *  Undefined (raw S3 objects that aren't tracked videos) renders a neutral dash. */
function StatusBadge({ status }: { status?: VideoSummary["status"] }) {
  const { t } = useTranslation();
  if (!status) return <span className="text-[var(--color-slate)]">—</span>;
  const map = {
    queued: { labelKey: "console.assets.status_queued", cls: "bg-[var(--color-powder)] text-[var(--color-gravel)]", Icon: Clock, spin: false },
    processing: { labelKey: "console.assets.status_indexing", cls: "bg-amber-50 text-amber-700", Icon: Loader2, spin: true },
    ready: { labelKey: "console.assets.status_ready", cls: "bg-emerald-50 text-emerald-700", Icon: CheckCircle2, spin: false },
    error: { labelKey: "console.assets.status_error", cls: "bg-red-50 text-red-700", Icon: AlertCircle, spin: false },
  } as const;
  const { labelKey, cls, Icon, spin } = map[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium", cls)}>
      <Icon size={12} className={cn(spin && "animate-spin")} />
      {t(labelKey)}
    </span>
  );
}

function formatBytes(b: number): string {
  if (!b) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = b;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i ? 1 : 0)} ${u[i]}`;
}

function s3Kind(name: string): "video" | "image" | "audio" | null {
  const lower = name.toLowerCase();
  if (/\.(mp4|mov|webm|mkv|avi)$/.test(lower)) return "video";
  if (/\.(png|jpe?g|webp|gif|bmp|tiff)$/.test(lower)) return "image";
  if (/\.(mp3|wav|m4a|flac|ogg|aac)$/.test(lower)) return "audio";
  return null;
}

function fmtSec(s: number | null | undefined): string | undefined {
  if (s == null) return undefined;
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m ${r.toString().padStart(2, "0")}s`;
}

export default function Assets() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: videos = [], isPending: videosLoading } = useVideosQuery();
  const { data: s3Items = [] } = useS3ObjectsQuery();
  const [thumbs, setThumbs] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<Filter>("all");
  const [filterOpen, setFilterOpen] = useState(false);
  const [view, setView] = useState<ViewMode>("list");
  const [query, setQuery] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [upload, setUpload] = useState<{
    total: number;
    done: number;
    name: string;
    pct: number;
    failed: number;
  } | null>(null);
  const uploading = upload != null;
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    await Promise.allSettled([
      qc.invalidateQueries({ queryKey: qk.videos(user?.id) }),
      qc.invalidateQueries({ queryKey: qk.s3(user?.id) }),
    ]);
  }, [qc, user?.id]);

  // Poster thumbnail is written at upload, so fetch one for every video (not
  // just ready ones). A 404 (no frame yet) just leaves the placeholder icon.
  useEffect(() => {
    videos.slice(0, 48).forEach(async (v) => {
      if (thumbs[v.id]) return;
      try {
        const url = await getPosterUrl(v.id);
        setThumbs((t) => ({ ...t, [v.id]: url }));
      } catch {
        /* no frame yet */
      }
    });
  }, [videos, thumbs]);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files) return;
      const vids = Array.from(files).filter((f) => f.type.startsWith("video/"));
      if (vids.length === 0) return;
      setUpload({ total: vids.length, done: 0, name: vids[0].name, pct: 0, failed: 0 });
      let failed = 0;
      for (let i = 0; i < vids.length; i++) {
        const f = vids[i];
        setUpload((u) => (u ? { ...u, name: f.name, pct: 0 } : u));
        try {
          await uploadVideo(f, (pct) => setUpload((u) => (u ? { ...u, pct } : u)));
        } catch {
          failed += 1;
        }
        setUpload((u) => (u ? { ...u, done: i + 1, failed } : u));
        await refresh(); // surface each new row (status "Queued") as it lands
      }
      // Hold the "done" state briefly so the user sees N/N, then dismiss.
      setTimeout(() => setUpload(null), 1800);
    },
    [refresh],
  );

  const rows: AssetRow[] = useMemo(() => {
    const videoRows: AssetRow[] = videos.map((v) => ({
      id: v.id,
      name: v.original_filename,
      kind: "video",
      durationLabel: fmtSec(v.duration_s),
      thumbUrl: thumbs[v.id],
      size: v.size_bytes ? formatBytes(v.size_bytes) : undefined,
      modified: v.created_at,
      status: v.status,
    }));
    const s3Rows: AssetRow[] = s3Items
      .map((it): AssetRow | null => {
        const kind = s3Kind(it.name);
        if (!kind) return null;
        return {
          id: `s3:${it.key}`,
          name: it.name,
          kind,
          durationLabel: fmtSec(it.duration_s ?? null),
          thumbUrl: it.thumb_url ?? undefined,
          size: formatBytes(it.size),
          modified: it.last_modified,
        };
      })
      .filter((x): x is AssetRow => x != null);

    const all = [...videoRows, ...s3Rows];
    const filtered = filter === "all" ? all : all.filter((r) => r.kind === filter);
    const queried = query
      ? filtered.filter((r) => r.name.toLowerCase().includes(query.toLowerCase()))
      : filtered;
    return queried;
  }, [videos, s3Items, thumbs, filter, query]);

  const counts = useMemo(() => {
    const v = videos.length + s3Items.filter((i) => s3Kind(i.name) === "video").length;
    const im = s3Items.filter((i) => s3Kind(i.name) === "image").length;
    const a = s3Items.filter((i) => s3Kind(i.name) === "audio").length;
    return { v, im, a };
  }, [videos, s3Items]);

  const filterLabels: Record<Filter, string> = {
    all: t("console.assets.filter_all"),
    video: t("console.assets.filter_video"),
    image: t("console.assets.filter_image"),
    audio: t("console.assets.filter_audio"),
  };

  return (
    <div className="mx-auto max-w-[1180px] px-8 py-6">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <h1 className="text-[32px] font-light tracking-[-0.64px] text-[var(--color-obsidian)]">
            {t("console.assets.title")}
          </h1>
          <Info size={14} className="text-[var(--color-slate)]" />
        </div>

        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <PillButton
            variant="ghost"
            rightIcon={<Upload size={14} />}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {upload
              ? t("console.assets.uploading", { done: upload.done, total: upload.total })
              : t("console.assets.upload_btn")}
          </PillButton>
          <button className="grid h-9 w-9 place-items-center rounded-full border border-[var(--color-chalk)] bg-white text-[var(--color-gravel)] hover:bg-[var(--color-powder)]">
            <ChevronDown size={14} />
          </button>
        </div>
      </div>

      <p className="mb-5 max-w-[680px] text-[12px] text-[var(--color-gravel)]">
        {t("console.assets.desc")}
      </p>

      <div className="mb-3 flex items-center gap-3">
        <div className="relative max-w-[420px] flex-1">
          <SearchIcon
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-slate)]"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("console.assets.filter_placeholder")}
            className="h-9 w-full rounded-full border border-[var(--color-chalk)] bg-white pl-9 pr-3 text-[13px] text-[var(--color-obsidian)] placeholder:text-[var(--color-slate)] focus:outline-none focus:ring-2 focus:ring-[var(--color-obsidian)]/10"
          />
        </div>

        <div className="relative ml-auto">
          <button
            onClick={() => setFilterOpen((o) => !o)}
            className="inline-flex h-9 items-center gap-2 rounded-full border border-transparent px-3 text-[13px] text-[var(--color-gravel)] hover:bg-[var(--color-powder)]"
          >
            <span className="text-[var(--color-slate)]">{t("console.assets.filter_by")}</span>
            <span className="text-[var(--color-obsidian)]">
              {filter === "all" ? t("console.assets.filter_file_type") : filterLabels[filter]}
            </span>
            <ChevronDown size={13} />
          </button>
          {filterOpen && (
            <div className="absolute right-0 top-10 z-10 w-40 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
              {(["all", "video", "image", "audio"] as Filter[]).map((k) => (
                <button
                  key={k}
                  onClick={() => {
                    setFilter(k);
                    setFilterOpen(false);
                  }}
                  className={cn(
                    "block w-full rounded-md px-3 py-1.5 text-left text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                    filter === k && "bg-[var(--color-powder)] font-medium",
                  )}
                >
                  {filterLabels[k]}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="inline-flex h-9 items-center overflow-hidden rounded-full border border-[var(--color-chalk)] bg-white">
          <button
            onClick={() => setView("grid")}
            className={cn(
              "grid h-9 w-9 place-items-center text-[var(--color-gravel)] hover:bg-[var(--color-powder)]",
              view === "grid" && "bg-[var(--color-powder)] text-[var(--color-obsidian)]",
            )}
          >
            <LayoutGrid size={14} />
          </button>
          <button
            onClick={() => setView("list")}
            className={cn(
              "grid h-9 w-9 place-items-center text-[var(--color-gravel)] hover:bg-[var(--color-powder)]",
              view === "list" && "bg-[var(--color-powder)] text-[var(--color-obsidian)]",
            )}
          >
            <ListIcon size={14} />
          </button>
        </div>
      </div>

      <div className="mb-5 flex items-center gap-5 text-[13px] text-[var(--color-gravel)]">
        <span className="inline-flex items-center gap-1.5">
          <Film size={13} /> {t("console.assets.count_videos", { count: counts.v })}
        </span>
        <span className="text-[var(--color-chalk)]">·</span>
        <span className="inline-flex items-center gap-1.5">
          <ImageIcon size={13} /> {t("console.assets.count_images", { count: counts.im })}
        </span>
        <span className="text-[var(--color-chalk)]">·</span>
        <span className="inline-flex items-center gap-1.5">
          <Music2 size={13} /> {t("console.assets.count_audios", { count: counts.a })}
        </span>
      </div>

      {videosLoading && rows.length === 0 ? (
        <div className="flex items-center justify-center gap-2 py-24 text-sm text-[var(--color-gravel)]">
          <Loader2 size={16} className="animate-spin" /> {t("console.assets.loading")}
        </div>
      ) : rows.length === 0 ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          className={cn(
            "flex flex-col items-center justify-center rounded-[18px] border border-dashed border-[var(--color-chalk)] bg-gradient-warm py-24 transition-colors",
            dragOver && "border-[var(--color-obsidian)]",
          )}
        >
          <button
            onClick={() => fileInputRef.current?.click()}
            className="grid h-12 w-12 place-items-center rounded-full bg-white shadow-hairline hover:bg-[var(--color-powder)]"
          >
            <Upload size={18} />
          </button>
          <p className="mt-4 text-[16px] font-medium text-[var(--color-obsidian)]">
            {t("console.assets.drop_label")}
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-[11px] text-[var(--color-gravel)]">
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              {t("console.assets.limit_audio")}
            </span>
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              {t("console.assets.limit_video")}
            </span>
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              {t("console.assets.limit_image")}
            </span>
          </div>
        </div>
      ) : view === "list" ? (
        <div className="overflow-hidden rounded-[14px] border border-[var(--color-chalk)] bg-white">
          <table className="w-full text-[13px]">
            <thead className="bg-[var(--color-powder)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--color-gravel)]">
              <tr>
                <th className="w-[68px] px-4 py-3"></th>
                <th className="px-4 py-3">{t("console.assets.col_name")}</th>
                <th className="w-[100px] px-4 py-3">{t("console.assets.col_type")}</th>
                <th className="w-[120px] px-4 py-3">{t("console.assets.col_status")}</th>
                <th className="w-[120px] px-4 py-3">{t("console.assets.col_duration")}</th>
                <th className="w-[120px] px-4 py-3">{t("console.assets.col_size")}</th>
                <th className="w-[140px] px-4 py-3">{t("console.assets.col_modified")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-[var(--color-chalk)] transition hover:bg-[var(--color-powder)]/60"
                >
                  <td className="px-4 py-2.5">
                    <div className="relative grid h-9 w-12 place-items-center overflow-hidden rounded-md bg-[var(--color-powder)] text-[var(--color-slate)]">
                      {r.thumbUrl ? (
                        <img src={r.thumbUrl} alt="" className="h-full w-full object-cover" />
                      ) : r.kind === "video" ? (
                        <Play size={14} />
                      ) : r.kind === "image" ? (
                        <ImageIcon size={14} />
                      ) : (
                        <Music2 size={14} />
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--color-obsidian)]">{r.name}</td>
                  <td className="px-4 py-2.5 capitalize text-[var(--color-gravel)]">{r.kind}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={r.status} /></td>
                  <td className="px-4 py-2.5 text-[var(--color-gravel)]">{r.durationLabel ?? "—"}</td>
                  <td className="px-4 py-2.5 text-[var(--color-gravel)]">{r.size ?? "—"}</td>
                  <td className="px-4 py-2.5 text-[var(--color-gravel)]">
                    {r.modified ? new Date(r.modified).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {rows.map((r) => (
            <div key={r.id} className="group cursor-pointer">
              <div className="relative h-[120px] overflow-hidden rounded-[14px] border border-[var(--color-chalk)] bg-[var(--color-powder)] transition-all group-hover:rounded-[18px] group-hover:shadow-hairline">
                {r.thumbUrl ? (
                  <img src={r.thumbUrl} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="grid h-full w-full place-items-center text-[var(--color-slate)]">
                    {r.kind === "video" ? <Play size={20} /> : r.kind === "image" ? <ImageIcon size={20} /> : <Music2 size={20} />}
                  </div>
                )}
                {r.durationLabel && (
                  <span className="absolute bottom-2 right-2 rounded-md bg-black/55 px-1.5 py-0.5 text-[10px] text-white">
                    {r.durationLabel}
                  </span>
                )}
                {r.status && r.status !== "ready" && (
                  <span className="absolute left-2 top-2">
                    <StatusBadge status={r.status} />
                  </span>
                )}
              </div>
              <p className="mt-2 truncate text-[13px] text-[var(--color-obsidian)]">{r.name}</p>
            </div>
          ))}
        </div>
      )}

      {upload && (
        <div className="fixed bottom-6 right-6 z-50 w-[320px] rounded-2xl border border-[var(--color-chalk)] bg-white p-4 shadow-hairline">
          <div className="mb-2 flex items-center gap-2">
            {upload.done >= upload.total ? (
              <CheckCircle2 size={15} className="text-emerald-600" />
            ) : (
              <Loader2 size={15} className="animate-spin text-[var(--color-obsidian)]" />
            )}
            <span className="text-[13px] font-medium text-[var(--color-obsidian)]">
              {upload.done >= upload.total
                ? (upload.total === 1
                    ? t("console.assets.upload_done_one", { total: upload.total })
                    : t("console.assets.upload_done_other", { total: upload.total }))
                : t("console.assets.upload_progress", { current: upload.done + 1, total: upload.total })}
            </span>
            <span className="ml-auto text-[12px] tabular-nums text-[var(--color-gravel)]">
              {upload.done}/{upload.total}
            </span>
          </div>
          {upload.done < upload.total && (
            <>
              <p className="mb-2 truncate text-[12px] text-[var(--color-gravel)]">{upload.name}</p>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-powder)]">
                <div
                  className="h-full rounded-full bg-[var(--color-obsidian)] transition-all"
                  style={{ width: `${upload.pct}%` }}
                />
              </div>
            </>
          )}
          {upload.failed > 0 && (
            <p className="mt-2 text-[11px] text-red-600">
              {t("console.assets.upload_failed", { count: upload.failed })}
            </p>
          )}
          <p className="mt-2 text-[11px] text-[var(--color-slate)]">
            {t("console.assets.upload_background")}
          </p>
        </div>
      )}
    </div>
  );
}

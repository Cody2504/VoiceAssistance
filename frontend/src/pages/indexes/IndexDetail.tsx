import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import {
  Check,
  ChevronDown,
  Copy,
  Hourglass,
  LayoutGrid,
  ListFilter,
  MoreVertical,
  Play,
  Plus,
  Rows3,
  Sparkles,
  SquareArrowRight,
  Trash2,
  Waypoints,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";

import {
  addVideoToIndex,
  deleteIndex,
  getIndex,
  listIndexVideos,
  removeVideoFromIndex,
  type IndexSummary,
  type IndexVideoEntry,
} from "@/apis/indexes.api";
import { uploadVideo } from "@/apis/videos.api";
import { qk, useVideosQuery } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import { VideoThumb } from "@/components/video/VideoThumb";
import { cn, formatSeconds } from "@/lib/utils";
import { IndexVideoPreviewModal } from "./IndexVideoPreviewModal";
import { VideoDropZone } from "./VideoDropZone";

type SortKey = "recent" | "name" | "duration";
type ViewMode = "list" | "grid";

const PAGE_LIMITS = [12, 24, 48];

function fmtHMS(s: number | null | undefined): string {
  if (s == null) return "—";
  const sec = Math.round(s);
  const h = String(Math.floor(sec / 3600)).padStart(2, "0");
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
  const ss = String(sec % 60).padStart(2, "0");
  return `${h}:${m}:${ss}`;
}

function fmtUsage(totalS: number): string {
  const h = Math.floor(totalS / 3600);
  const m = Math.round((totalS % 3600) / 60);
  if (h > 0) return `${h} hr ${m} min`;
  if (m > 0) return `${m} min`;
  return `${Math.round(totalS)} sec`;
}

function fmtDate(iso: string | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  });
}

/** TwelveLabs-style page list: 1 2 3 4 5 … N with a sliding window. */
function pageWindow(current: number, total: number): Array<number | "…"> {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

export default function IndexDetail() {
  const { t } = useTranslation();
  const { indexId } = useParams<{ indexId: string }>();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  // "default" is the virtual library index (TwelveLabs' "My Index (Default)"):
  // same UI, backed by the whole video library instead of index membership.
  const isDefault = indexId === "default";

  const [summary, setSummary] = useState<IndexSummary | null>(null);
  const [memberItems, setMemberItems] = useState<IndexVideoEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("recent");
  const [sortOpen, setSortOpen] = useState(false);
  const [limitOpen, setLimitOpen] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [kebabOpen, setKebabOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [idCopied, setIdCopied] = useState(false);
  const [uploadingNames, setUploadingNames] = useState<string[]>([]);
  const [previewPos, setPreviewPos] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const mode: ViewMode = params.get("mode") === "grid" ? "grid" : "list";
  const page = Math.max(1, parseInt(params.get("page") ?? "1", 10) || 1);
  const limitParam = parseInt(params.get("page_limit") ?? "12", 10);
  const pageLimit = PAGE_LIMITS.includes(limitParam) ? limitParam : 12;

  const setParam = useCallback(
    (key: "mode" | "page" | "page_limit", value: string) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set(key, value);
          if (key !== "page") next.set("page", "1");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  // Global videos list — the data source for the default index, and the
  // created_at join for real indexes (membership rows carry no upload date).
  const qc = useQueryClient();
  const { user } = useAuth();
  const { data: allVideos = [] } = useVideosQuery();
  const videoById = useMemo(() => new Map(allVideos.map((v) => [v.id, v])), [allVideos]);

  const reload = useCallback(async () => {
    setError(null);
    // The join/source data is served from a 5-min-stale persisted cache;
    // without this the Date-uploaded column shows "—" for fresh uploads.
    qc.invalidateQueries({ queryKey: qk.videos(user?.id) });
    if (!indexId || isDefault) return;
    try {
      const [s, v] = await Promise.all([getIndex(indexId), listIndexVideos(indexId)]);
      setSummary(s);
      setMemberItems(v);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("console.index_detail.error_load"));
    }
  }, [indexId, isDefault, t, qc, user?.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Real indexes: re-poll membership while any video is still ingesting.
  // (The default index polls via useVideosQuery's own refetchInterval.)
  useEffect(() => {
    if (isDefault) return;
    if (!memberItems.some((v) => v.status === "queued" || v.status === "processing")) return;
    const timer = setTimeout(() => reload(), 5000);
    return () => clearTimeout(timer);
  }, [isDefault, memberItems, reload]);

  const items: IndexVideoEntry[] = useMemo(
    () =>
      isDefault
        ? allVideos.map((v, i) => ({
            video_id: v.id,
            position: i,
            original_filename: v.original_filename,
            duration_s: v.duration_s,
            status: v.status,
          }))
        : memberItems,
    [isDefault, allVideos, memberItems],
  );

  const videoCount = isDefault ? allVideos.length : (summary?.video_count ?? items.length);
  const totalDuration = isDefault
    ? allVideos.reduce((s, v) => s + (v.duration_s ?? 0), 0)
    : (summary?.total_duration_s ?? 0);
  const title = isDefault
    ? t("console.indexes.default_title")
    : summary?.title || t("console.index_detail.untitled");

  const handleUploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      setError(null);
      setUploadingNames((prev) => [...prev, ...files.map((f) => f.name)]);
      const uploadOne = async (f: File) => {
        try {
          const v = await uploadVideo(f);
          if (!isDefault && indexId) await addVideoToIndex(indexId, v.id);
        } catch (e) {
          setError(
            e instanceof Error
              ? t("console.index_detail.upload_failed", { name: f.name, message: e.message })
              : t("console.index_detail.upload_failed_short", { name: f.name }),
          );
        } finally {
          setUploadingNames((prev) => prev.filter((n) => n !== f.name));
        }
      };
      await Promise.all(files.map(uploadOne));
      reload();
    },
    [indexId, isDefault, reload, t],
  );

  const handleRemove = async (videoId: string) => {
    if (!indexId || isDefault) return;
    if (!confirm(t("console.index_detail.remove_confirm"))) return;
    try {
      await removeVideoFromIndex(indexId, videoId);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("console.index_detail.error_remove"));
    }
  };

  const handleDeleteIndex = async () => {
    if (!indexId || isDefault || !summary) return;
    if (!confirm(t("console.indexes.delete_confirm", { title: summary.title ?? "" }))) return;
    try {
      await deleteIndex(indexId);
      navigate("/indexes");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("console.index_detail.error_load"));
    }
  };

  const copyIndexId = async () => {
    if (!indexId || isDefault) return;
    try {
      await navigator.clipboard.writeText(indexId);
      setIdCopied(true);
      setTimeout(() => setIdCopied(false), 1500);
    } catch {
      /* clipboard unavailable — ignore */
    }
  };

  const goAnalyze = useCallback(
    (videoId: string) => {
      navigate(`/playground/analyze?index_id=${isDefault ? "default" : indexId}&video_id=${videoId}`);
    },
    [navigate, indexId, isDefault],
  );

  // Filter + sort over the full list; pagination is applied after.
  const sorted = useMemo(() => {
    const filtered = filter
      ? items.filter((v) => v.original_filename.toLowerCase().includes(filter.toLowerCase()))
      : [...items];
    filtered.sort((a, b) => {
      if (sortKey === "name") return a.original_filename.localeCompare(b.original_filename);
      if (sortKey === "duration") return (b.duration_s ?? 0) - (a.duration_s ?? 0);
      const ca = videoById.get(a.video_id)?.created_at ?? "";
      const cb = videoById.get(b.video_id)?.created_at ?? "";
      return cb.localeCompare(ca);
    });
    return filtered;
  }, [items, filter, sortKey, videoById]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageLimit));
  const safePage = Math.min(page, pageCount);
  const pageRows = sorted.slice((safePage - 1) * pageLimit, safePage * pageLimit);

  const sortLabels: Record<SortKey, string> = {
    recent: t("console.index_detail.sort_recent"),
    name: t("console.index_detail.sort_name"),
    duration: t("console.index_detail.sort_duration"),
  };

  // Sliding underline under the active (Videos) tab, like the reference.
  const videosTabRef = useRef<HTMLSpanElement | null>(null);
  const [underline, setUnderline] = useState<{ left: number; width: number }>({ left: 0, width: 0 });
  const tabVideosLabel = t("console.index_detail.tab_videos");
  useLayoutEffect(() => {
    const measure = () => {
      const el = videosTabRef.current;
      if (el) setUnderline({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [tabVideosLabel]);

  if (!indexId) return null;

  const scopeQuery = `?index_id=${isDefault ? "default" : indexId}`;
  const tabs = [
    { key: "search", label: t("console.index_detail.tab_search"), href: `/playground/search${scopeQuery}` },
    { key: "analyze", label: t("console.index_detail.tab_analyze"), href: `/playground/analyze${scopeQuery}` },
    { key: "segment", label: t("console.index_detail.tab_segment"), href: "/playground/segment" },
  ];

  const isEmpty = items.length === 0 && uploadingNames.length === 0;

  return (
    <div className="mx-auto max-w-[1180px] px-8">
      {/* ── sticky header: title row + tab bar ── */}
      <div className="sticky top-0 z-20 -mx-8 bg-[#fdfcfc] px-8 pt-6">
        <div className="mb-5 flex items-start justify-between">
          <div className="flex items-center gap-5">
            <h1 className="max-w-[480px] truncate text-[24px] font-medium tracking-[-0.3px] text-[var(--color-obsidian)]">
              {title}
            </h1>
            {!isDefault && (
              <button
                onClick={copyIndexId}
                className="group inline-flex items-center gap-1 text-[14px] text-[var(--color-obsidian)] transition hover:text-[var(--color-gravel)]"
              >
                {idCopied ? (
                  <Check size={16} className="text-emerald-600" />
                ) : (
                  <Copy size={16} className="text-[var(--color-gravel)]" />
                )}
                {idCopied ? t("console.index_detail.copied") : t("console.index_detail.index_id_label")}
              </button>
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
                if (e.target.files) {
                  handleUploadFiles(
                    Array.from(e.target.files).filter(
                      (f) => f.type.startsWith("video/") || /\.(mp4|mov|webm|mkv)$/i.test(f.name),
                    ),
                  );
                }
                e.target.value = "";
              }}
            />
            {!isDefault && (
              <button
                onClick={() => navigate(`/indexes/${indexId}/graph`)}
                className="inline-flex items-center gap-1.5 rounded-[12px] border border-[var(--color-chalk)] px-4 py-2 text-[13px] text-[var(--color-obsidian)] transition-all hover:rounded-[16px] hover:bg-[var(--color-powder)]"
              >
                <Waypoints size={14} />
                {t("console.index_detail.knowledge_graph_btn")}
              </button>
            )}
            <div className="relative">
              <button
                onClick={() => setAddMenuOpen((o) => !o)}
                className="inline-flex items-center gap-1.5 rounded-[12px] bg-[var(--color-obsidian)] px-4 py-2 text-[13px] text-white transition-all hover:rounded-[16px] hover:bg-neutral-800"
              >
                <Plus size={14} />
                {t("console.index_detail.add_video")}
                <ChevronDown size={14} />
              </button>
              {addMenuOpen && (
                <div className="absolute right-0 top-11 z-30 w-44 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
                  <button
                    onClick={() => {
                      setAddMenuOpen(false);
                      fileInputRef.current?.click();
                    }}
                    className="block w-full rounded-md px-3 py-1.5 text-left text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
                  >
                    {t("console.index_detail.upload_files")}
                  </button>
                  {!isDefault && (
                    <button
                      onClick={() => {
                        setAddMenuOpen(false);
                        setLibraryOpen(true);
                      }}
                      className="block w-full rounded-md px-3 py-1.5 text-left text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
                    >
                      {t("console.index_detail.add_from_library")}
                    </button>
                  )}
                </div>
              )}
            </div>
            {!isDefault && (
              <div className="relative">
                <button
                  onClick={() => setKebabOpen((o) => !o)}
                  className="grid h-9 w-9 place-items-center rounded-md text-[var(--color-gravel)] transition hover:bg-[var(--color-powder)]"
                >
                  <MoreVertical size={16} />
                </button>
                {kebabOpen && (
                  <div className="absolute right-0 top-10 z-30 w-40 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
                    <button
                      onClick={() => {
                        setKebabOpen(false);
                        handleDeleteIndex();
                      }}
                      className="block w-full rounded-md px-3 py-1.5 text-left text-[13px] text-rose-600 hover:bg-rose-50"
                    >
                      {t("console.index_detail.delete_index")}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* tab bar — icons + sliding underline per the reference */}
        <div className="relative flex h-12 items-end gap-6 border-b border-[var(--color-chalk)]">
          <span
            ref={videosTabRef}
            className="mb-4 inline-flex items-center gap-1 px-1 text-[16px] font-medium text-[var(--color-obsidian)]"
          >
            <Play size={18} />
            {t("console.index_detail.tab_videos")}
          </span>
          {tabs.map((tab) => (
            <Link
              key={tab.key}
              to={tab.href}
              className="mb-4 px-1 text-[16px] text-[var(--color-obsidian)]/70 transition hover:text-[var(--color-obsidian)]"
            >
              {tab.label}
            </Link>
          ))}
          <div
            className="absolute bottom-0 border-b border-[var(--color-obsidian)] transition-all duration-300"
            style={{ left: underline.left, width: underline.width }}
          />
        </div>
      </div>

      <div className="py-5">
        {error && (
          <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[13px] text-rose-700">
            {error}
          </div>
        )}

        {isEmpty ? (
          <>
            <div className="mb-5 flex items-center gap-x-2 text-[13px] text-[var(--color-gravel)]">
              <Play size={18} className="text-[var(--color-slate)]" />
              <span>{t("console.index_detail.videos_meta", { count: 0 })}</span>
              <span className="h-1 w-1 rounded-full bg-[var(--color-slate)]" />
              <Hourglass size={16} className="text-[var(--color-slate)]" />
              <span>{fmtUsage(0)}</span>
            </div>
            <VideoDropZone onFiles={handleUploadFiles} />
          </>
        ) : (
          <>
            {/* ── controls row: filter · sort · view toggle ── */}
            <div className="mb-3 flex items-center gap-x-2">
              <div className="flex flex-1">
                <div className="flex h-10 w-[212px] items-center gap-1 rounded-lg border border-[var(--color-chalk)] px-4 transition-colors focus-within:border-[var(--color-obsidian)] hover:border-[var(--color-slate)]">
                  <ListFilter size={18} className="shrink-0 text-[var(--color-slate)]" />
                  <input
                    value={filter}
                    onChange={(e) => {
                      setFilter(e.target.value);
                      setParam("page", "1");
                    }}
                    placeholder={t("console.index_detail.filter_videos_placeholder")}
                    className="h-full w-full border-none bg-transparent text-[13px] text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-slate)]"
                  />
                </div>
              </div>
              <p className="text-[13px] font-bold text-[var(--color-gravel)]">
                {t("console.indexes.sort_by")}
              </p>
              <div className="relative">
                <button
                  onClick={() => setSortOpen((o) => !o)}
                  className="inline-flex items-center gap-1 rounded-lg py-2 pl-2 pr-1 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
                >
                  {sortLabels[sortKey]}
                  <ChevronDown size={16} className="text-[var(--color-gravel)]" />
                </button>
                {sortOpen && (
                  <div className="absolute right-0 top-10 z-10 w-44 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
                    {(["recent", "name", "duration"] as SortKey[]).map((k) => (
                      <button
                        key={k}
                        onClick={() => {
                          setSortKey(k);
                          setSortOpen(false);
                          setParam("page", "1");
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
              <div className="flex h-7 items-center overflow-hidden rounded-[9.6px] border border-[var(--color-obsidian)]">
                <button
                  aria-label={t("console.index_detail.view_grid")}
                  onClick={() => setParam("mode", "grid")}
                  className={cn(
                    "flex h-full w-8 items-center justify-center transition",
                    mode === "grid"
                      ? "bg-[var(--color-obsidian)] text-white"
                      : "text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                  )}
                >
                  <LayoutGrid size={15} />
                </button>
                <button
                  aria-label={t("console.index_detail.view_list")}
                  onClick={() => setParam("mode", "list")}
                  className={cn(
                    "flex h-full w-8 items-center justify-center transition",
                    mode === "list"
                      ? "bg-[var(--color-obsidian)] text-white"
                      : "text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                  )}
                >
                  <Rows3 size={15} />
                </button>
              </div>
            </div>

            {/* ── usage line ── */}
            <div className="mb-5 flex items-center gap-x-2">
              <div className="flex items-center gap-x-1">
                <Play size={18} className="text-[var(--color-slate)]" />
                <p className="text-[13px] text-[var(--color-gravel)]">
                  {t("console.index_detail.videos_meta", { count: videoCount })}
                </p>
              </div>
              <div className="h-1 w-1 rounded-full bg-[var(--color-slate)]" />
              <div className="flex items-center gap-x-1">
                <Hourglass size={16} className="text-[var(--color-slate)]" />
                <p className="text-[13px] text-[var(--color-gravel)]">{fmtUsage(totalDuration)}</p>
              </div>
            </div>

            {/* ── list / grid ── */}
            {mode === "list" ? (
              <table className="w-full border-separate border-spacing-0">
                <thead>
                  <tr>
                    <th className="w-[136px] px-2 pb-2" />
                    <th className="max-w-[400px] px-2 pb-2 text-left">
                      <p className="text-[13px] font-bold text-[var(--color-obsidian)]">
                        {t("console.index_detail.col_title")}
                      </p>
                    </th>
                    <th className="px-2 pb-2 text-right">
                      <p className="text-[13px] font-bold text-[var(--color-obsidian)]">
                        {t("console.index_detail.col_duration")}
                      </p>
                    </th>
                    <th className="px-2 pb-2 text-right">
                      <p className="text-[13px] font-bold text-[var(--color-obsidian)]">
                        {t("console.index_detail.col_date")}
                      </p>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((v) => {
                    const globalPos = sorted.indexOf(v);
                    const created = videoById.get(v.video_id)?.created_at;
                    return (
                      <tr
                        key={v.video_id}
                        role="button"
                        onClick={() => setPreviewPos(globalPos)}
                        className="group/row cursor-pointer transition-colors duration-150 hover:bg-[var(--color-powder)]"
                      >
                        <td className="rounded-l-lg px-2 py-2">
                          <div className="h-[58px] w-[104px] overflow-hidden rounded-lg bg-neutral-800">
                            <VideoThumb videoId={v.video_id} className="h-full w-full rounded-none" />
                          </div>
                        </td>
                        <td className="max-w-[400px] px-2">
                          <div className="flex items-center justify-between gap-2">
                            <p
                              className="w-full truncate text-[13px] text-[var(--color-obsidian)]"
                              title={v.original_filename}
                            >
                              {v.original_filename}
                            </p>
                            {v.status !== "ready" && (
                              <span
                                className={cn(
                                  "shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px]",
                                  v.status === "error"
                                    ? "bg-rose-50 text-rose-600"
                                    : "bg-amber-50 text-amber-600",
                                )}
                              >
                                {v.status}
                              </span>
                            )}
                            <div className="flex w-28 shrink-0 items-center justify-end gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  goAnalyze(v.video_id);
                                }}
                                className="hidden items-center gap-1 whitespace-nowrap rounded-[8.4px] px-2 py-1 text-[12px] text-[var(--color-obsidian)] shadow-[0px_0px_0px_1px_var(--color-chalk)_inset] transition-all hover:bg-black/5 group-hover/row:inline-flex"
                              >
                                {t("console.index_detail.analyze_btn")}
                                <Sparkles size={13} />
                              </button>
                              {!isDefault && (
                                <button
                                  title={t("console.index_detail.remove_title")}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRemove(v.video_id);
                                  }}
                                  className="hidden rounded p-1 text-[var(--color-gravel)] transition hover:bg-rose-50 hover:text-rose-600 group-hover/row:block"
                                >
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-2 text-right text-[13px] text-[var(--color-obsidian)]">
                          {fmtHMS(v.duration_s)}
                        </td>
                        <td className="rounded-r-lg px-2 text-right text-[13px] text-[var(--color-obsidian)]">
                          {fmtDate(created)}
                        </td>
                      </tr>
                    );
                  })}
                  {uploadingNames.map((name) => (
                    <tr key={`uploading-${name}`} className="opacity-70">
                      <td className="px-2 py-2">
                        <div className="h-[58px] w-[104px] animate-pulse rounded-lg bg-[var(--color-powder)]" />
                      </td>
                      <td className="max-w-[400px] px-2">
                        <p className="truncate text-[13px] text-[var(--color-obsidian)]">{name}</p>
                        <span className="font-mono text-[11px] text-amber-600">
                          {t("console.index_detail.uploading")}
                        </span>
                      </td>
                      <td />
                      <td />
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 lg:grid-cols-4">
                {pageRows.map((v) => {
                  const globalPos = sorted.indexOf(v);
                  return (
                    <button
                      key={v.video_id}
                      onClick={() => setPreviewPos(globalPos)}
                      className="group/card text-left"
                    >
                      <div className="relative aspect-video overflow-hidden rounded-xl bg-neutral-800">
                        <VideoThumb videoId={v.video_id} className="h-full w-full rounded-none" />
                        <span className="absolute bottom-2 right-2 rounded bg-black/65 px-1.5 py-0.5 font-mono text-[10px] text-white">
                          {fmtHMS(v.duration_s)}
                        </span>
                      </div>
                      <p
                        className="mt-2 truncate text-[13px] text-[var(--color-obsidian)]"
                        title={v.original_filename}
                      >
                        {v.original_filename}
                      </p>
                    </button>
                  );
                })}
                {uploadingNames.map((name) => (
                  <div key={`uploading-${name}`} className="opacity-70">
                    <div className="aspect-video animate-pulse rounded-xl bg-[var(--color-powder)]" />
                    <p className="mt-2 truncate text-[13px] text-[var(--color-obsidian)]">{name}</p>
                  </div>
                ))}
              </div>
            )}

            {/* ── pagination + page size ── */}
            {(pageCount > 1 || sorted.length > 12) && (
              <div className="mt-10 flex items-center justify-center gap-x-5 py-5">
                <div className="flex items-center">
                  <button
                    disabled={safePage <= 1}
                    onClick={() => setParam("page", String(safePage - 1))}
                    className="flex h-10 w-10 items-center justify-center rounded-2xl text-[var(--color-obsidian)] transition disabled:text-[var(--color-slate)] [&>svg]:h-4 [&>svg]:w-4 enabled:hover:bg-[var(--color-powder)]"
                  >
                    <SquareArrowRight className="rotate-180" />
                  </button>
                  {pageWindow(safePage, pageCount).map((p, i) =>
                    p === "…" ? (
                      <span
                        key={`gap-${i}`}
                        className="flex h-10 w-10 items-center justify-center text-[13px] text-[var(--color-gravel)]"
                      >
                        …
                      </span>
                    ) : (
                      <button
                        key={p}
                        onClick={() => setParam("page", String(p))}
                        className={cn(
                          "flex h-10 w-10 items-center justify-center rounded-2xl text-[13px] text-[var(--color-obsidian)] transition",
                          p === safePage ? "bg-[var(--color-chalk)]" : "hover:bg-[var(--color-powder)]",
                        )}
                      >
                        {p}
                      </button>
                    ),
                  )}
                  <button
                    disabled={safePage >= pageCount}
                    onClick={() => setParam("page", String(safePage + 1))}
                    className="flex h-10 w-10 items-center justify-center rounded-2xl text-[var(--color-obsidian)] transition disabled:text-[var(--color-slate)] [&>svg]:h-4 [&>svg]:w-4 enabled:hover:bg-[var(--color-powder)]"
                  >
                    <SquareArrowRight />
                  </button>
                </div>
                <div className="relative">
                  <button
                    onClick={() => setLimitOpen((o) => !o)}
                    className="inline-flex items-center gap-1 rounded-lg py-2 pl-4 pr-2 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
                  >
                    {t("console.index_detail.per_page", { count: pageLimit })}
                    <ChevronDown size={16} className="text-[var(--color-gravel)]" />
                  </button>
                  {limitOpen && (
                    <div className="absolute bottom-11 right-0 z-10 w-32 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
                      {PAGE_LIMITS.map((l) => (
                        <button
                          key={l}
                          onClick={() => {
                            setLimitOpen(false);
                            setParam("page_limit", String(l));
                          }}
                          className={cn(
                            "block w-full rounded-md px-3 py-1.5 text-left text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                            l === pageLimit && "bg-[var(--color-powder)] font-medium",
                          )}
                        >
                          {t("console.index_detail.per_page", { count: l })}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <IndexVideoPreviewModal
        open={previewPos !== null}
        items={sorted}
        current={previewPos ?? 0}
        onNavigate={(i) => setPreviewPos(i)}
        onClose={() => setPreviewPos(null)}
        onAnalyze={goAnalyze}
      />

      {!isDefault && (
        <AddVideosModal
          open={libraryOpen}
          onClose={() => setLibraryOpen(false)}
          existingIds={new Set(items.map((i) => i.video_id))}
          onAdd={async (videoId) => {
            if (!indexId) return;
            await addVideoToIndex(indexId, videoId);
            reload();
          }}
        />
      )}
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
  const { t } = useTranslation();
  const { data: videos = [] } = useVideosQuery();
  const [busyId, setBusyId] = useState<string | null>(null);

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
          <h2 className="text-[15px] font-semibold text-neutral-900">
            {t("console.add_videos_modal.title")}
          </h2>
          <button onClick={onClose} className="rounded p-1 text-[var(--color-gravel)] hover:bg-neutral-100">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {available.length === 0 && (
            <div className="m-4 rounded-[14px] border border-dashed border-neutral-300 bg-neutral-50 p-6 text-center text-[13px] text-neutral-600">
              {t("console.add_videos_modal.empty")}
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

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { listS3Objects, presignS3, type S3Item } from "@/apis/s3.api";
import { cn, formatSeconds } from "@/lib/utils";

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 ? 0 : 1)} ${units[i]}`;
}

interface ThumbProps {
  item: S3Item;
  onClick: () => void;
}

function S3Thumb({ item, onClick }: ThumbProps) {
  const [errored, setErrored] = useState(false);
  const showImg = item.thumb_url && !errored;
  return (
    <div
      onClick={onClick}
      className="group relative aspect-video cursor-pointer overflow-hidden rounded-md bg-neutral-200 ring-1 ring-neutral-200 transition hover:ring-neutral-400"
    >
      {showImg && (
        <img
          src={item.thumb_url ?? undefined}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setErrored(true)}
          draggable={false}
        />
      )}
      {!showImg && (
        <div className="grid h-full w-full place-items-center text-xs text-neutral-500">
          {item.name}
        </div>
      )}
      {item.duration_s !== null && item.duration_s !== undefined && (
        <span className="absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-white">
          {formatSeconds(item.duration_s)}
        </span>
      )}
    </div>
  );
}

interface PreviewProps {
  item: S3Item | null;
  onClose: () => void;
}

function S3PreviewModal({ item, onClose }: PreviewProps) {
  const { t } = useTranslation();
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!item) { setUrl(null); setErr(null); return; }
    let alive = true;
    setUrl(null);
    setErr(null);
    presignS3(item.key)
      .then((u) => { if (alive) setUrl(u); })
      .catch((e: unknown) => {
        if (alive) setErr((e as Error)?.message ?? "presign failed");
      });
    return () => { alive = false; };
  }, [item]);

  if (!item) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-3xl overflow-hidden rounded-lg bg-black"
      >
        <button
          onClick={onClose}
          className="absolute right-3 top-3 z-10 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
        >
          <X size={16} />
        </button>
        {url ? (
          <video src={url} controls autoPlay className="aspect-video w-full" />
        ) : (
          <div className="aspect-video w-full grid place-items-center text-neutral-400">
            {err ?? t("console.preview.loading")}
          </div>
        )}
        <div className="bg-neutral-900 px-4 py-2 text-xs text-neutral-300">
          <p className="truncate" title={item.key}>{item.key}</p>
          <p className="text-neutral-500">
            {humanBytes(item.size)}
            {item.duration_s !== null && item.duration_s !== undefined && (
              <> &middot; {formatSeconds(item.duration_s)}</>
            )}
            {" "}&middot; {new Date(item.last_modified).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function S3TestPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<S3Item[] | null>(null);
  const [bucket, setBucket] = useState<string>("jockeyassistant");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<S3Item | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listS3Objects();
      setItems(r.items);
      setBucket(r.bucket);
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail
        ?? (e as Error)?.message
        ?? "failed to list bucket",
      );
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const totalBytes = useMemo(
    () => (items ?? []).reduce((acc, it) => acc + it.size, 0),
    [items],
  );

  return (
    <div className="mx-auto flex h-screen w-full max-w-6xl flex-col px-6 py-6">
      <header className="mb-5 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">
            {t("console.s3test.title", { bucket })}
          </h1>
          <p className="text-xs text-neutral-500">
            {t("console.s3test.desc_prefix")}{" "}
            <code className="rounded bg-neutral-100 px-1">videos/</code>{" "}
            {t("console.s3test.desc_prefix2")}{" "}
            <code className="rounded bg-neutral-100 px-1">thumbs/</code>
            {t("console.s3test.desc_suffix")}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-neutral-500">
          {items && (
            <span>
              {items.length === 1
                ? t("console.s3test.object_count_one", { count: items.length })
                : t("console.s3test.object_count_other", { count: items.length })}{" "}
              &middot; {humanBytes(totalBytes)}
            </span>
          )}
          <button
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2.5 py-1.5 text-xs font-medium text-neutral-700 hover:border-neutral-400 disabled:opacity-50"
          >
            <RefreshCw size={12} className={cn(loading && "animate-spin")} />
            {t("console.s3test.refresh")}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <p className="font-medium">{t("console.s3test.error_title")}</p>
          <p className="mt-0.5 break-all">{error}</p>
          <p className="mt-1 text-red-600/70">
            {t("console.s3test.error_hint")}
          </p>
        </div>
      )}

      <div className="grid flex-1 grid-cols-2 gap-4 overflow-auto pr-1 sm:grid-cols-3 lg:grid-cols-4">
        {items === null && (
          <div className="col-span-full grid place-items-center py-10 text-xs text-neutral-400">
            {t("console.s3test.loading_bucket")}
          </div>
        )}
        {items?.length === 0 && !error && (
          <div className="col-span-full grid place-items-center py-10 text-xs text-neutral-400">
            {t("console.s3test.empty_bucket")}
          </div>
        )}
        {items?.map((it) => (
          <article key={it.key} className="space-y-2">
            <S3Thumb item={it} onClick={() => setPreview(it)} />
            <div className="space-y-0.5 text-xs leading-tight">
              <p className="truncate text-neutral-900" title={it.name}>{it.name}</p>
              <p className="text-neutral-500">
                {humanBytes(it.size)}
                {it.duration_s !== null && it.duration_s !== undefined && (
                  <> &middot; {formatSeconds(it.duration_s)}</>
                )}
                {" "}&middot; {t("console.s3test.label_video")}
              </p>
            </div>
          </article>
        ))}
      </div>

      <S3PreviewModal item={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

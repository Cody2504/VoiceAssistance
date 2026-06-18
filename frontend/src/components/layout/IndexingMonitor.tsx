import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { Loader2, ListChecks } from "lucide-react";
import { listVideos, type VideoSummary } from "@/apis/videos.api";

type Counts = { indexing: number; indexed: number; failed: number };

/**
 * Topbar indexing monitor. Polls the user's videos and rolls their statuses up
 * into Indexing / Indexed / Failed counts. Polls every 5s while anything is
 * indexing, backing off to 30s when idle. Click the pill to see the breakdown.
 */
export function IndexingMonitor() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [counts, setCounts] = useState<Counts>({ indexing: 0, indexed: 0, failed: 0 });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const vids: VideoSummary[] = await listVideos();
        if (!alive) return;
        const c: Counts = { indexing: 0, indexed: 0, failed: 0 };
        for (const v of vids) {
          if (v.status === "queued" || v.status === "processing") c.indexing += 1;
          else if (v.status === "ready") c.indexed += 1;
          else if (v.status === "error") c.failed += 1;
        }
        setCounts(c);
        timer.current = setTimeout(tick, c.indexing > 0 ? 5000 : 30000);
      } catch {
        if (alive) timer.current = setTimeout(tick, 30000);
      }
    };
    tick();
    return () => {
      alive = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const active = counts.indexing > 0;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="indexing-monitor"
        onClick={() => setOpen((o) => !o)}
        className="grid h-8 min-w-[40px] place-items-center rounded-lg bg-black/5 px-2 text-[13px] text-[var(--color-obsidian)] transition hover:bg-black/10"
      >
        {active ? (
          <span className="flex items-center gap-1">
            {counts.indexing}
            <Loader2 size={14} className="animate-spin" />
          </span>
        ) : (
          <ListChecks size={16} />
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-40 min-w-[300px] rounded-2xl bg-white p-4 shadow-[0px_14px_24px_-10px_rgba(21,6,46,0.25)]">
          <p className="text-[15px] font-semibold text-[var(--color-obsidian)]">
            {t("layout.monitor.title")}
          </p>
          <p className="mt-1 text-[12px] text-[var(--color-gravel)]">{t("layout.monitor.window")}</p>
          <div className="mt-3 flex divide-x divide-grey-300 rounded-lg border border-grey-300">
            <Cell n={counts.indexing} label={t("layout.monitor.indexing")} />
            <Cell n={counts.indexed} label={t("layout.monitor.indexed")} />
            <Cell n={counts.failed} label={t("layout.monitor.failed")} />
          </div>
          <Link
            to="/indexes"
            onClick={() => setOpen(false)}
            className="mt-4 block rounded-xl bg-grey-700 py-2 text-center text-[13px] text-grey-50 transition hover:bg-grey-700/80"
          >
            {t("layout.monitor.go_to_indexes")}
          </Link>
        </div>
      )}
    </div>
  );
}

function Cell({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex-1 px-3 py-2 text-center">
      <span className="font-semibold text-[var(--color-obsidian)]">{n}</span>{" "}
      <span className="text-[12px] text-[var(--color-gravel)]">{label}</span>
    </div>
  );
}

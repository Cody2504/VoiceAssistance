import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Info, ArrowRight, Search as SearchIcon, ChevronDown, X, Play, MoreVertical } from "lucide-react";
import { PillButton } from "@/components/ui/PillButton";
import { listVideos, type VideoSummary } from "@/apis/videos.api";
import { cn } from "@/lib/utils";

type SortKey = "recent" | "name" | "duration";

interface IndexCardData {
  id: string;
  title: string;
  videos: number;
  durationLabel: string;
  createdAt: string;
  variant: "default" | "sample-mix" | "sample-ads" | "sample-edu" | "sample-social" | "sample-sports";
  href?: string;
  sortableTime: number;
}

function fmtDuration(totalSec: number): string {
  if (totalSec < 60) return `${Math.round(totalSec)}s`;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function IndexCard({ data }: { data: IndexCardData }) {
  const tile = {
    default: "bg-gradient-warm",
    "sample-mix": "bg-gradient-to-br from-amber-100 via-orange-100 to-emerald-100",
    "sample-ads": "bg-gradient-to-br from-rose-100 via-pink-100 to-violet-100",
    "sample-edu": "bg-gradient-to-br from-sky-100 via-cyan-100 to-emerald-100",
    "sample-social": "bg-gradient-to-br from-amber-100 via-rose-100 to-sky-100",
    "sample-sports": "bg-gradient-to-br from-lime-100 via-emerald-100 to-orange-100",
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
          {data.videos} {data.videos === 1 ? "Video" : "Videos"} ({data.durationLabel})
        </div>
      </div>
      <div className="mt-3 flex items-start justify-between">
        <div>
          <h4 className="text-[15px] font-medium text-[var(--color-obsidian)]">{data.title}</h4>
          <p className="mt-0.5 text-[12px] text-[var(--color-gravel)]">{data.createdAt}</p>
        </div>
        <button
          className="opacity-0 transition group-hover:opacity-100"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
        >
          <MoreVertical size={16} className="text-[var(--color-gravel)]" />
        </button>
      </div>
    </div>
  );

  return data.href ? (
    <Link to={data.href}>{body}</Link>
  ) : (
    body
  );
}

export default function Indexes() {
  const navigate = useNavigate();
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("recent");
  const [bannerVisible, setBannerVisible] = useState(true);
  const [sortOpen, setSortOpen] = useState(false);

  useEffect(() => {
    listVideos()
      .then(setVideos)
      .catch(() => setVideos([]));
  }, []);

  const cards: IndexCardData[] = useMemo(() => {
    const totalDuration = videos.reduce((s, v) => s + (v.duration_s ?? 0), 0);
    const defaultCard: IndexCardData = {
      id: "default",
      title: "My Index (Default)",
      videos: videos.length,
      durationLabel: videos.length ? fmtDuration(totalDuration) : "0s",
      createdAt: `Created on ${new Date().toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })}`,
      variant: "default",
      href: "/playground/library",
      sortableTime: Date.now(),
    };
    const samples: IndexCardData[] = [
      { id: "s1", title: "Sample Index: Mix", videos: 161, durationLabel: "8h 35m", createdAt: "Sample · Apr 03, 2026", variant: "sample-mix", sortableTime: Date.parse("2026-04-03") },
      { id: "s2", title: "Sample Index: Ads", videos: 27, durationLabel: "47m 7s", createdAt: "Sample · Mar 21, 2026", variant: "sample-ads", sortableTime: Date.parse("2026-03-21") },
      { id: "s3", title: "Sample Index: E Learning", videos: 24, durationLabel: "2h 41m", createdAt: "Sample · Mar 12, 2026", variant: "sample-edu", sortableTime: Date.parse("2026-03-12") },
      { id: "s4", title: "Sample Index: Social Media", videos: 15, durationLabel: "2h 17m", createdAt: "Sample · Mar 04, 2026", variant: "sample-social", sortableTime: Date.parse("2026-03-04") },
      { id: "s5", title: "Sample Index: Sports", videos: 19, durationLabel: "2h 15m", createdAt: "Sample · Feb 20, 2026", variant: "sample-sports", sortableTime: Date.parse("2026-02-20") },
    ];
    const all = [defaultCard, ...samples];

    const filtered = filter
      ? all.filter((c) => c.title.toLowerCase().includes(filter.toLowerCase()))
      : all;

    const sorted = [...filtered].sort((a, b) => {
      if (sortKey === "name") return a.title.localeCompare(b.title);
      if (sortKey === "duration") return b.videos - a.videos;
      return b.sortableTime - a.sortableTime;
    });
    return sorted;
  }, [videos, filter, sortKey]);

  const sortLabel = { recent: "Recent upload", name: "Name (A→Z)", duration: "Video count" }[sortKey];

  return (
    <div className="mx-auto max-w-[1180px] px-8 py-6">
      <div className="mb-6 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-[32px] font-light tracking-[-0.64px] text-[var(--color-obsidian)]">
            My indexes
          </h1>
          <Info size={14} className="text-[var(--color-slate)]" />
        </div>
        <PillButton
          variant="ghost"
          rightIcon={<ArrowRight size={14} />}
          onClick={() => navigate("/indexes")}
          disabled
          title="Index creation coming soon"
        >
          Create Index
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
            placeholder="Filter by index name"
            className="h-9 w-full rounded-full border border-[var(--color-chalk)] bg-white pl-9 pr-3 text-[13px] text-[var(--color-obsidian)] placeholder:text-[var(--color-slate)] focus:outline-none focus:ring-2 focus:ring-[var(--color-obsidian)]/10"
          />
        </div>

        <div className="relative">
          <button
            onClick={() => setSortOpen((o) => !o)}
            className="inline-flex h-9 items-center gap-2 rounded-full border border-transparent px-3 text-[13px] text-[var(--color-gravel)] hover:bg-[var(--color-powder)]"
          >
            <span className="text-[var(--color-slate)]">Sort by</span>
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
                  {{ recent: "Recent upload", name: "Name (A→Z)", duration: "Video count" }[k]}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {bannerVisible && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-[#bce5b6] bg-[#dff5d8] px-4 py-2.5 text-[12px] text-[#1e5a23]">
          <Info size={14} className="shrink-0" />
          You are currently on the Free Plan, which means that your index will expire 90 days after it was created.
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
          <IndexCard key={c.id} data={c} />
        ))}
      </div>

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

import { useEffect, useState } from "react";
import { FolderSearch, Search as SearchIcon, X } from "lucide-react";
import { listVideos } from "@/apis/videos.api";
import { cn } from "@/lib/utils";

interface IndexEntry {
  id: string;
  title: string;
  meta: string;
  variant: "default" | "mix" | "ads" | "edu" | "social" | "sports";
  sample?: boolean;
}

const variantClass: Record<IndexEntry["variant"], string> = {
  default: "bg-gradient-warm",
  mix: "bg-gradient-to-br from-amber-100 via-orange-100 to-emerald-100",
  ads: "bg-gradient-to-br from-rose-100 via-pink-100 to-violet-100",
  edu: "bg-gradient-to-br from-sky-100 via-cyan-100 to-emerald-100",
  social: "bg-gradient-to-br from-amber-100 via-rose-100 to-sky-100",
  sports: "bg-gradient-to-br from-lime-100 via-emerald-100 to-orange-100",
};

interface Props {
  selectedIndexId?: string;
  onSelect: (idx: { id: string; title: string }) => void;
}

/**
 * Index picker used by Search. Closed state mirrors the TwelveLabs reference:
 * a looping video clip behind a "Select an index" pill, with a soft warm/cool
 * inner-glow and hover-zoom on the video. Opens a modal of indexes (real
 * default + sample tiles).
 */
export function IndexPicker({ selectedIndexId, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [count, setCount] = useState(0);

  useEffect(() => {
    listVideos().then((v) => setCount(v.length)).catch(() => setCount(0));
  }, []);

  const entries: IndexEntry[] = [
    { id: "default", title: "My Index (Default)", meta: `${count} Videos`, variant: "default" },
    { id: "sample-sports", title: "Sample Index: Sports", meta: "19 Videos (2h 15m)", variant: "sports", sample: true },
    { id: "sample-social", title: "Sample Index: Social Media", meta: "15 Videos (2h 17m)", variant: "social", sample: true },
    { id: "sample-mix", title: "Sample Index: Mix", meta: "161 Videos (8h 35m)", variant: "mix", sample: true },
    { id: "sample-edu", title: "Sample Index: E Learning", meta: "24 Videos (2h 41m)", variant: "edu", sample: true },
    { id: "sample-ads", title: "Sample Index: Ads", meta: "27 Videos (47m 7s)", variant: "ads", sample: true },
  ];

  const filtered = filter
    ? entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()))
    : entries;

  const selected = entries.find((e) => e.id === selectedIndexId) ?? null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group/panel relative block aspect-video w-full overflow-hidden rounded-[18px] border border-[var(--color-chalk)] bg-black transition hover:shadow-hairline"
      >
        {selected ? (
          <div
            className={cn(
              "absolute inset-0 grid place-items-center",
              variantClass[selected.variant],
            )}
          >
            <div className="flex flex-col items-center gap-2 text-[var(--color-obsidian)]">
              <span className="text-[15px] font-medium">{selected.title}</span>
              <span className="text-[12px] text-[var(--color-gravel)]">{selected.meta}</span>
              <span className="mt-2 rounded-full bg-[var(--color-obsidian)] px-3 py-1 text-[12px] text-white">
                Change index
              </span>
            </div>
          </div>
        ) : (
          <>
            <video
              autoPlay
              loop
              muted
              playsInline
              preload="auto"
              className="absolute left-1/2 top-1/2 h-full w-full -translate-x-1/2 -translate-y-1/2 object-cover transition-transform duration-200 ease-in-out group-hover/panel:scale-[1.2]"
            >
              <source src="/twelvelabs/index-loop.mp4" type="video/mp4" />
            </video>
            <div className="absolute inset-0 bg-black/35" aria-hidden="true" />
            <div
              className="absolute inset-0 rounded-[18px]"
              aria-hidden="true"
              style={{
                boxShadow:
                  "inset -4px -4px 41px 0 rgba(253, 227, 162, 0.65), inset 4px 4px 41px 0 rgba(168, 230, 178, 0.65)",
              }}
            />
            <span className="absolute left-1/2 top-1/2 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-[8px] bg-[var(--color-obsidian)] px-3 py-1.5 text-[13px] font-medium text-white transition-all duration-200 hover:rounded-[12px] hover:bg-neutral-800">
              Select an index
              <FolderSearch size={14} />
            </span>
          </>
        )}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-6"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[85vh] w-full max-w-[1080px] overflow-hidden rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[var(--color-chalk)] bg-[var(--color-powder)] px-6 py-4">
              <h2 className="text-[16px] font-semibold text-[var(--color-obsidian)]">
                Select an index to Search
              </h2>
              <button onClick={() => setOpen(false)} className="rounded p-1 text-[var(--color-gravel)] hover:bg-white">
                <X size={16} />
              </button>
            </div>
            <div className="flex items-center gap-3 px-6 py-4">
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
              <span className="ml-auto text-[12px] text-[var(--color-gravel)]">
                Sort by <span className="text-[var(--color-obsidian)]">Recent upload</span>
              </span>
            </div>
            <div className="grid max-h-[60vh] grid-cols-1 gap-5 overflow-y-auto px-6 pb-6 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((e) => (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => {
                    onSelect({ id: e.id, title: e.title });
                    setOpen(false);
                  }}
                  className="group text-left"
                >
                  <div
                    className={cn(
                      "relative h-[170px] overflow-hidden border border-[var(--color-chalk)] transition-all duration-200 ease-out",
                      "rounded-[16px] group-hover:rounded-[22px] group-hover:shadow-hairline",
                      variantClass[e.variant],
                    )}
                  >
                    <div className="absolute bottom-3 left-3 rounded-md bg-black/55 px-2 py-1 text-[11px] text-white">
                      {e.meta}
                    </div>
                  </div>
                  <h4 className="mt-2 text-[14px] font-medium text-[var(--color-obsidian)]">{e.title}</h4>
                  {e.sample && (
                    <p className="text-[11px] text-[var(--color-gravel)]">Sample</p>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

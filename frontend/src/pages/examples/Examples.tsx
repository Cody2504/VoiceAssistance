import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { ChevronDown, RefreshCw, Sparkles, ListTree } from "lucide-react";
import { cn } from "@/lib/utils";

type Kind = "search" | "analyze" | "segment";
type FilterValue = "all" | Kind;

interface ExampleEntry {
  id: string;
  kind: Kind;
  title: string;
  tags: string[];
  route: string;
}

const EXAMPLES: ExampleEntry[] = [
  // Search
  { id: "viral",      kind: "search",  title: "Find that viral clip all your friends are talking about but don't remember its title", tags: ["Content Recommendation", "User Engagement"], route: "/playground/search" },
  { id: "objects",    kind: "search",  title: "Search exact number of objects",                                                       tags: ["Sports Analytics", "Object Counting"],     route: "/playground/search" },
  { id: "logos",      kind: "search",  title: "Detect logos and text on screen",                                                       tags: ["Product Search", "Brand Analytics"],       route: "/playground/search" },
  { id: "products",   kind: "search",  title: "Find products and how they are mentioned within videos",                                tags: ["E-Commerce", "Brand Analytics"],           route: "/playground/search" },
  { id: "sounds",     kind: "search",  title: "Listen for specific sounds",                                                            tags: ["Content Analysis", "Music Understanding"], route: "/playground/search" },
  { id: "highlights", kind: "search",  title: "Engage fans through fun video highlights",                                              tags: ["Fan Engagement", "Sports"],                route: "/playground/search" },
  // Analyze
  { id: "describe",   kind: "analyze", title: "Generate video description that fits your needs",     tags: ["Fan Engagement", "Sports"],                       route: "/playground/analyze" },
  { id: "police",     kind: "analyze", title: "Create a police report with exact timestamps",        tags: ["Security"],                                       route: "/playground/analyze" },
  { id: "visual",     kind: "analyze", title: "Analyse visual components for insights and inspiration", tags: ["Content Analysis", "Q&A", "Advertisement"],     route: "/playground/analyze" },
  { id: "recs",       kind: "analyze", title: "Make content based recommendations",                  tags: ["Content Recommendation", "Media & Entertainment"], route: "/playground/analyze" },
  { id: "deeper",     kind: "analyze", title: "Understand the visual elements on a deeper level",    tags: ["Content Analysis", "Media & Entertainment", "Q&A"], route: "/playground/analyze" },
  { id: "moderate",   kind: "analyze", title: "Moderate content based on your target audience",      tags: ["Content Moderation", "Media & Entertainment"],     route: "/playground/analyze" },
  { id: "ask",        kind: "analyze", title: "Ask anything specific about the video",               tags: ["Q&A", "Social Media"],                            route: "/playground/analyze" },
  // Segment
  { id: "product-loc", kind: "segment", title: "Locate every moment your product appears on screen", tags: ["Brand Analytics", "E-Commerce", "Advertisement"],  route: "/playground/segment" },
  { id: "speakers",    kind: "segment", title: "Identify every speaker turn throughout your video",  tags: ["Content Analysis", "Media & Entertainment"],       route: "/playground/segment" },
  { id: "game",        kind: "segment", title: "Break down game footage by play type and key moments", tags: ["Sports Analytics", "Fan Engagement"],            route: "/playground/segment" },
];

const KIND_LABEL: Record<Kind, string> = {
  search: "Search",
  analyze: "Analyze",
  segment: "Segment",
};

// Mirrors the TwelveLabs light-X / dark-X palette per category.
const KIND_STYLE: Record<
  Kind,
  {
    hoverBg: string;
    chipBg: string;
    chipBorder: string;
    chipIconClass: string;
    featTag: string;
    Icon: typeof RefreshCw;
  }
> = {
  search: {
    hoverBg: "group-hover:bg-[#fbdfff]",
    chipBg: "bg-[#fbdfff]",
    chipBorder: "border-[#7b5880]",
    chipIconClass: "text-[#7b5880]",
    featTag: "bg-[#fbdfff] border-[#7b5880] text-[#7b5880]",
    Icon: RefreshCw,
  },
  analyze: {
    hoverBg: "group-hover:bg-[#fde3a2]",
    chipBg: "bg-[#fde3a2]",
    chipBorder: "border-[#7d5d0c]",
    chipIconClass: "text-[#7d5d0c]",
    featTag: "bg-[#fde3a2] border-[#7d5d0c] text-[#7d5d0c]",
    Icon: Sparkles,
  },
  segment: {
    hoverBg: "group-hover:bg-[#c4eefe]",
    chipBg: "bg-[#c4eefe]",
    chipBorder: "border-[#26586d]",
    chipIconClass: "text-[#26586d]",
    featTag: "bg-[#c4eefe] border-[#26586d] text-[#26586d]",
    Icon: ListTree,
  },
};

export default function Examples() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<FilterValue>("all");
  const [filterOpen, setFilterOpen] = useState(false);

  const visible = useMemo(
    () => (filter === "all" ? EXAMPLES : EXAMPLES.filter((e) => e.kind === filter)),
    [filter],
  );

  return (
    <div className="mx-auto max-w-[1180px] px-8 py-8">
      <h1 className="max-w-[820px] text-[26px] font-light leading-[1.25] tracking-[-0.4px] text-[var(--color-obsidian)]">
        We've curated and pre-indexed videos from various industries.
        <br />
        Dive right in and try our features.
      </h1>

      <div className="mt-7 flex items-center gap-2">
        <span className="text-[13px] text-[var(--color-gravel)]">Filter by examples</span>
        <div className="relative">
          <button
            onClick={() => setFilterOpen((o) => !o)}
            className="inline-flex h-9 w-44 items-center justify-between gap-2 rounded-lg border border-[var(--color-chalk)] bg-white px-3 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
          >
            <span className="capitalize">{filter === "all" ? "All" : KIND_LABEL[filter]}</span>
            <ChevronDown size={14} />
          </button>
          {filterOpen && (
            <div className="absolute left-0 top-10 z-10 w-44 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-hairline">
              {(["all", "search", "analyze", "segment"] as FilterValue[]).map((k) => (
                <button
                  key={k}
                  onClick={() => {
                    setFilter(k);
                    setFilterOpen(false);
                  }}
                  className={cn(
                    "block w-full rounded-md px-3 py-1.5 text-left text-[13px] capitalize text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                    filter === k && "bg-[var(--color-powder)] font-medium",
                  )}
                >
                  {k === "all" ? "All" : KIND_LABEL[k as Kind]}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-5 pb-12 md:grid-cols-2 lg:grid-cols-3">
        {visible.map((ex) => {
          const style = KIND_STYLE[ex.kind];
          const Icon = style.Icon;
          return (
            <button
              key={ex.id}
              onClick={() => navigate(ex.route)}
              className="group relative h-[280px] w-full overflow-hidden rounded-[60px] border border-[var(--color-chalk)] bg-[var(--color-powder)]/60 text-left transition-[border-radius,box-shadow] duration-200 ease-out hover:rounded-[80px] hover:shadow-hairline"
            >
              {/* Hover fill — full card color on hover */}
              <div
                aria-hidden="true"
                className={cn("absolute inset-0 transition-colors duration-200", style.hoverBg)}
              />
              <div className="relative z-10 flex h-full flex-col gap-3 px-7 py-7">
                <div className="flex items-start gap-3">
                  <span
                    className={cn(
                      "grid h-8 w-8 shrink-0 place-items-center rounded-[8px] border",
                      style.chipBg,
                      style.chipBorder,
                    )}
                  >
                    <Icon size={16} className={style.chipIconClass} strokeWidth={2} />
                  </span>
                </div>
                <h3 className="line-clamp-4 text-[17px] font-normal leading-[1.3] text-[var(--color-obsidian)]">
                  {ex.title}
                </h3>
                <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
                  <span
                    className={cn(
                      "inline-flex items-center rounded border px-1 py-[3px] text-[10px] font-normal uppercase tracking-[0.06em]",
                      style.featTag,
                    )}
                  >
                    {KIND_LABEL[ex.kind]}
                  </span>
                  {ex.tags.map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center rounded border border-[var(--color-obsidian)] px-1 py-[3px] text-[10px] font-normal uppercase tracking-[0.06em] text-[var(--color-obsidian)]"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

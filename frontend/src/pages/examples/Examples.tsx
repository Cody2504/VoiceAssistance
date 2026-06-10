import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { ChevronDown, RefreshCw, Sparkles, ListTree } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

type Kind = "search" | "analyze" | "segment";
type FilterValue = "all" | Kind;

interface ExampleEntry {
  id: string;
  kind: Kind;
  titleKey: string;
  tagKeys: string;
  route: string;
}

const EXAMPLES: ExampleEntry[] = [
  // Search
  { id: "viral",      kind: "search",  titleKey: "marketing.examples.examples.viral_title",      tagKeys: "marketing.examples.examples.viral_tags",      route: "/playground/search" },
  { id: "objects",    kind: "search",  titleKey: "marketing.examples.examples.objects_title",    tagKeys: "marketing.examples.examples.objects_tags",    route: "/playground/search" },
  { id: "logos",      kind: "search",  titleKey: "marketing.examples.examples.logos_title",      tagKeys: "marketing.examples.examples.logos_tags",      route: "/playground/search" },
  { id: "products",   kind: "search",  titleKey: "marketing.examples.examples.products_title",   tagKeys: "marketing.examples.examples.products_tags",   route: "/playground/search" },
  { id: "sounds",     kind: "search",  titleKey: "marketing.examples.examples.sounds_title",     tagKeys: "marketing.examples.examples.sounds_tags",     route: "/playground/search" },
  { id: "highlights", kind: "search",  titleKey: "marketing.examples.examples.highlights_title", tagKeys: "marketing.examples.examples.highlights_tags", route: "/playground/search" },
  // Analyze
  { id: "describe",   kind: "analyze", titleKey: "marketing.examples.examples.describe_title",   tagKeys: "marketing.examples.examples.describe_tags",   route: "/playground/analyze" },
  { id: "police",     kind: "analyze", titleKey: "marketing.examples.examples.police_title",     tagKeys: "marketing.examples.examples.police_tags",     route: "/playground/analyze" },
  { id: "visual",     kind: "analyze", titleKey: "marketing.examples.examples.visual_title",     tagKeys: "marketing.examples.examples.visual_tags",     route: "/playground/analyze" },
  { id: "recs",       kind: "analyze", titleKey: "marketing.examples.examples.recs_title",       tagKeys: "marketing.examples.examples.recs_tags",       route: "/playground/analyze" },
  { id: "deeper",     kind: "analyze", titleKey: "marketing.examples.examples.deeper_title",     tagKeys: "marketing.examples.examples.deeper_tags",     route: "/playground/analyze" },
  { id: "moderate",   kind: "analyze", titleKey: "marketing.examples.examples.moderate_title",   tagKeys: "marketing.examples.examples.moderate_tags",   route: "/playground/analyze" },
  { id: "ask",        kind: "analyze", titleKey: "marketing.examples.examples.ask_title",        tagKeys: "marketing.examples.examples.ask_tags",        route: "/playground/analyze" },
  // Segment
  { id: "product-loc", kind: "segment", titleKey: "marketing.examples.examples.product_loc_title", tagKeys: "marketing.examples.examples.product_loc_tags", route: "/playground/segment" },
  { id: "speakers",    kind: "segment", titleKey: "marketing.examples.examples.speakers_title",    tagKeys: "marketing.examples.examples.speakers_tags",    route: "/playground/segment" },
  { id: "game",        kind: "segment", titleKey: "marketing.examples.examples.game_title",        tagKeys: "marketing.examples.examples.game_tags",        route: "/playground/segment" },
];

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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<FilterValue>("all");
  const [filterOpen, setFilterOpen] = useState(false);

  const KIND_LABEL: Record<Kind, string> = {
    search: t("marketing.examples.kind_search"),
    analyze: t("marketing.examples.kind_analyze"),
    segment: t("marketing.examples.kind_segment"),
  };

  const visible = useMemo(
    () => (filter === "all" ? EXAMPLES : EXAMPLES.filter((e) => e.kind === filter)),
    [filter],
  );

  return (
    <div className="mx-auto max-w-[1180px] px-8 py-8">
      <h1 className="max-w-[820px] text-[26px] font-light leading-[1.25] tracking-[-0.4px] text-[var(--color-obsidian)]">
        {t("marketing.examples.heading").split("\n").map((line, i, arr) => (
          <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
        ))}
      </h1>

      <div className="mt-7 flex items-center gap-2">
        <span className="text-[13px] text-[var(--color-gravel)]">{t("marketing.examples.filter_label")}</span>
        <div className="relative">
          <button
            onClick={() => setFilterOpen((o) => !o)}
            className="inline-flex h-9 w-44 items-center justify-between gap-2 rounded-lg border border-[var(--color-chalk)] bg-white px-3 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
          >
            <span className="capitalize">{filter === "all" ? t("marketing.examples.filter_all") : KIND_LABEL[filter]}</span>
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
                  {k === "all" ? t("marketing.examples.filter_all") : KIND_LABEL[k as Kind]}
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
          const tags = t(ex.tagKeys).split(",");
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
                  {t(ex.titleKey)}
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
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center rounded border border-[var(--color-obsidian)] px-1 py-[3px] text-[10px] font-normal uppercase tracking-[0.06em] text-[var(--color-obsidian)]"
                    >
                      {tag}
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

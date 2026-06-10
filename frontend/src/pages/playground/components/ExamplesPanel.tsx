import { RefreshCw, Sparkles, ListTree } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export interface ExampleTile<P = Record<string, unknown>> {
  id: string;
  title: string;
  /** Optional i18n key. When present, resolved via t() and shown instead of `title`. */
  titleKey?: string;
  tags: string[];
  preset: P;
}

type Kind = "search" | "analyze" | "segment";

/**
 * Per-kind color palette reproducing TwelveLabs' light/dark variants
 * (light-purple/dark-purple for Search, light-orange/dark-orange for Analyze,
 * light-blue/dark-blue for Segment/Embed).
 */
const KIND_STYLE: Record<
  Kind,
  {
    Icon: typeof RefreshCw;
    /** English fallback label (used for tag filtering logic). */
    label: string;
    /** i18n key for the displayed kind label. */
    labelKey: string;
    /** Hover fill applied to the whole card. */
    hoverBg: string;
    /** Icon chip background and stroke. */
    chipBg: string;
    chipBorder: string;
    chipIconClass: string;
    /** Featured (first) tag — colored to match the section. */
    featTag: string;
  }
> = {
  search: {
    Icon: RefreshCw,
    label: "Search",
    labelKey: "layout.sidebar.search",
    hoverBg: "group-hover:bg-[#fbdfff]",
    chipBg: "bg-[#fbdfff]",
    chipBorder: "border-[#7b5880]",
    chipIconClass: "text-[#7b5880]",
    featTag: "bg-[#fbdfff] border-[#7b5880] text-[#7b5880]",
  },
  analyze: {
    Icon: Sparkles,
    label: "Analyze",
    labelKey: "layout.sidebar.analyze",
    hoverBg: "group-hover:bg-[#fde3a2]",
    chipBg: "bg-[#fde3a2]",
    chipBorder: "border-[#7d5d0c]",
    chipIconClass: "text-[#7d5d0c]",
    featTag: "bg-[#fde3a2] border-[#7d5d0c] text-[#7d5d0c]",
  },
  segment: {
    Icon: ListTree,
    label: "Segment",
    labelKey: "layout.sidebar.segment",
    hoverBg: "group-hover:bg-[#c4eefe]",
    chipBg: "bg-[#c4eefe]",
    chipBorder: "border-[#26586d]",
    chipIconClass: "text-[#26586d]",
    featTag: "bg-[#c4eefe] border-[#26586d] text-[#26586d]",
  },
};

interface Props<P> {
  examples: ExampleTile<P>[];
  onSelect: (preset: P) => void;
  kind: Kind;
}

/**
 * Example tile reproducing the TwelveLabs playground card:
 * neutral gray default, fills with the section color on hover; small icon
 * chip top-left; tags row at bottom with the section-colored "kind" tag
 * featured first and remaining tags rendered as outlined neutral chips.
 */
export function ExamplesPanel<P>({ examples, onSelect, kind }: Props<P>) {
  const { t } = useTranslation();
  const style = KIND_STYLE[kind];
  const Icon = style.Icon;
  const kindLabel = t(style.labelKey);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {examples.map((ex) => (
        <button
          key={ex.id}
          type="button"
          onClick={() => onSelect(ex.preset)}
          className="group relative h-[170px] w-full overflow-hidden rounded-[24px] border border-[var(--color-chalk)] bg-[var(--color-powder)]/60 text-left transition-[box-shadow] duration-200 ease-out hover:shadow-hairline"
        >
          {/* Inner hover-fill layer */}
          <div
            className={cn("absolute inset-0 transition-colors duration-200", style.hoverBg)}
            aria-hidden="true"
          />
          <div className="relative z-10 flex h-full flex-col gap-2 px-4 py-5">
            <div className="flex items-start gap-2">
              <span
                className={cn(
                  "grid h-6 w-6 shrink-0 place-items-center rounded-[5px] border",
                  style.chipBg,
                  style.chipBorder,
                )}
              >
                <Icon size={12} className={style.chipIconClass} strokeWidth={2} />
              </span>
              <p className="line-clamp-3 text-[13px] font-normal leading-[1.4] text-[var(--color-obsidian)]">
                {ex.titleKey ? t(ex.titleKey) : ex.title}
              </p>
            </div>
            <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
              <span
                className={cn(
                  "inline-flex items-center rounded border px-1 py-[2px] text-[9px] font-normal uppercase tracking-[0.06em]",
                  style.featTag,
                )}
              >
                {kindLabel}
              </span>
              {ex.tags
                .filter((tag) => tag.toLowerCase() !== style.label.toLowerCase())
                .map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center rounded border border-[var(--color-obsidian)] px-1 py-[2px] text-[9px] font-normal uppercase tracking-[0.06em] text-[var(--color-obsidian)]"
                  >
                    {tag}
                  </span>
                ))}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

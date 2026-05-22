import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SampleAppCard {
  title: string;
  body: string;
  language: "Python" | "Node";
  href: string;
}

interface Props {
  /** Big centered heading e.g. "What do you want to find?" */
  heading: string;
  /** Small subtitle e.g. "Try 'search' with a Sample App" */
  subtitle: string;
  seeAllHref?: string;
  cards: SampleAppCard[];
  /** Pastel panel color matching the adjacent capability section */
  panelClass: string;
  /** Border / tag stroke color used inside each panel */
  strokeClass: string;
}

/**
 * "What do you want to …" separator strip used between capability sections.
 * Three pastel sample-app cards with PYTHON / NODE tags, body copy, and a
 * "See all sample apps" pill in the top-right — mirrors the TwelveLabs
 * product-overview separator blocks.
 */
export function SampleApps({ heading, subtitle, seeAllHref = "#", cards, panelClass, strokeClass }: Props) {
  return (
    <section className="mx-auto max-w-[1200px] px-6 py-20">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div className="text-center md:text-left">
          <h3 className="text-[28px] font-light tracking-[-0.5px] text-[var(--color-obsidian)] md:text-[32px]">
            {heading}
          </h3>
          <p className="mt-2 text-[13px] text-[var(--color-gravel)]">{subtitle}</p>
        </div>
        <a
          href={seeAllHref}
          className="inline-flex h-10 items-center gap-1.5 rounded-full border border-[var(--color-chalk)] bg-white px-5 text-[13px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
        >
          See all sample apps <ArrowUpRight size={13} />
        </a>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        {cards.map((c) => (
          <a
            key={c.title}
            href={c.href}
            target="_blank"
            rel="noreferrer"
            className={cn(
              "group flex h-[280px] flex-col p-6 transition-all duration-200 ease-out",
              "rounded-[44px] hover:rounded-[60px]",
              panelClass,
            )}
          >
            <span
              className={cn(
                "self-start rounded-md border bg-transparent px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]",
                strokeClass,
              )}
            >
              {c.language}
            </span>
            <h4 className="mt-4 text-[18px] font-medium leading-[1.3] text-[var(--color-obsidian)]">
              {c.title}
            </h4>
            <p className="mt-auto pt-5 text-[13px] leading-[1.5] text-[var(--color-obsidian)]/75">
              {c.body}
            </p>
          </a>
        ))}
      </div>
    </section>
  );
}

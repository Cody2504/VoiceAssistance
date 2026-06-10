import { useTranslation } from "react-i18next";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SampleAppCard {
  titleKey: string;
  bodyKey: string;
  language: "Python" | "Node";
  href: string;
}

interface Props {
  /** i18n key for the big centered heading e.g. "landing.sample_apps.search_heading" */
  headingKey: string;
  /** i18n key for the small subtitle */
  subtitleKey: string;
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
export function SampleApps({ headingKey, subtitleKey, seeAllHref = "#", cards, panelClass, strokeClass }: Props) {
  const { t } = useTranslation();
  return (
    <section className="mx-auto max-w-[1200px] px-6 py-20">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div className="text-center md:text-left">
          <h3 className="text-[28px] font-light tracking-[-0.5px] text-[var(--color-obsidian)] md:text-[32px]">
            {t(headingKey)}
          </h3>
          <p className="mt-2 text-[13px] text-[var(--color-gravel)]">{t(subtitleKey)}</p>
        </div>
        <a
          href={seeAllHref}
          className="inline-flex h-10 items-center gap-1.5 rounded-full border border-[var(--color-chalk)] bg-white px-5 text-[13px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
        >
          {t("landing.sample_apps.see_all")} <ArrowUpRight size={13} />
        </a>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        {cards.map((c) => (
          <a
            key={c.titleKey}
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
              {t(c.titleKey)}
            </h4>
            <p className="mt-auto pt-5 text-[13px] leading-[1.5] text-[var(--color-obsidian)]/75">
              {t(c.bodyKey)}
            </p>
          </a>
        ))}
      </div>
    </section>
  );
}

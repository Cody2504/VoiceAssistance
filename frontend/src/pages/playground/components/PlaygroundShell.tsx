import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * TwelveLabs-style two-column playground page. Title left, "Learn" pill right.
 * Left = form card; right = large centered headline + "Start with an example"
 * grid (rendered by examplesPanel). Results, if any, render below the grid.
 */
export function PlaygroundShell({
  title,
  subtitle,
  formPanel,
  examplesPanel,
  browsePanel,
  resultsPanel,
  wide,
}: {
  title: string;
  subtitle: string;
  formPanel: ReactNode;
  examplesPanel: ReactNode;
  /** When provided, the right column renders this full-bleed (no headline /
   *  "start with an example") — used to browse a selected index's videos. */
  browsePanel?: ReactNode;
  resultsPanel?: ReactNode;
  /** Widen the left form column (e.g. Analyze, for a larger video preview). */
  wide?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="h-full overflow-y-auto bg-[var(--color-eggshell)]">
      <div className="mx-auto max-w-[1200px] px-8 py-8">
        <header className="mb-6 flex items-start justify-between">
          <h1 className="text-[32px] font-light tracking-[-0.64px] text-[var(--color-obsidian)]">
            {title}
          </h1>
          <button className="inline-flex h-9 items-center gap-2 rounded-full border border-[var(--color-chalk)] bg-white px-4 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]">
            <span aria-hidden="true">📒</span>
            {t("pgkit.shell.learn")} <ChevronDown size={12} />
          </button>
        </header>

        <div
          className={
            wide
              ? "grid gap-8 lg:grid-cols-[minmax(0,600px)_minmax(0,1fr)]"
              : "grid gap-8 lg:grid-cols-[minmax(0,460px)_minmax(0,1fr)]"
          }
        >
          <section>{formPanel}</section>
          {browsePanel ? (
            <section className="pt-1">{browsePanel}</section>
          ) : (
            <section className="flex flex-col items-center pt-4">
              <h2 className="max-w-[640px] text-center text-[24px] font-normal tracking-[-0.3px] text-[var(--color-obsidian)]">
                {subtitle}
              </h2>
              <p className="mt-3 text-[13px] text-[var(--color-gravel)]">{t("pgkit.shell.start_with_example")}</p>
              <div className="mt-6 w-full">{examplesPanel}</div>
            </section>
          )}
        </div>

        {resultsPanel && <section className="mt-10">{resultsPanel}</section>}
      </div>
    </div>
  );
}

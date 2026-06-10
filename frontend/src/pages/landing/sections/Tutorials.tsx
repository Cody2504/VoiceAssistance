import { useTranslation } from "react-i18next";
import { ArrowUpRight, BookOpen, Github } from "lucide-react";

interface Card {
  titleKey: string;
  blurbKey: string;
  tutorial: string;
  code: string;
  tagKey: string;
}

const CARDS: Card[] = [
  {
    titleKey: "landing.tutorials.card1_title",
    blurbKey: "landing.tutorials.card1_blurb",
    tutorial: "#",
    code: "#",
    tagKey: "landing.tutorials.card1_tag",
  },
  {
    titleKey: "landing.tutorials.card2_title",
    blurbKey: "landing.tutorials.card2_blurb",
    tutorial: "#",
    code: "#",
    tagKey: "landing.tutorials.card2_tag",
  },
  {
    titleKey: "landing.tutorials.card3_title",
    blurbKey: "landing.tutorials.card3_blurb",
    tutorial: "#",
    code: "#",
    tagKey: "landing.tutorials.card3_tag",
  },
  {
    titleKey: "landing.tutorials.card4_title",
    blurbKey: "landing.tutorials.card4_blurb",
    tutorial: "#",
    code: "#",
    tagKey: "landing.tutorials.card4_tag",
  },
];

export function Tutorials() {
  const { t } = useTranslation();
  return (
    <section id="tutorials" className="mx-auto max-w-[1200px] px-6 py-24">
      <header className="mb-12 text-center">
        <h2 className="mx-auto max-w-[720px] text-[40px] font-light leading-[1.08] tracking-[-1px] text-[var(--color-obsidian)] md:text-[48px]">
          {t("landing.tutorials.h2")}
        </h2>
        <p className="mx-auto mt-5 max-w-[560px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          {t("landing.tutorials.sub")}
        </p>
      </header>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map((c) => (
          <div
            key={c.titleKey}
            className="flex flex-col rounded-[20px] border border-[var(--color-chalk)] bg-white p-5 transition-[box-shadow] duration-200 ease-out hover:shadow-hairline"
          >
            <span className="self-start rounded-md bg-[var(--color-powder)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--color-gravel)]">
              {t(c.tagKey)}
            </span>
            <h3 className="mt-4 text-[16px] font-medium leading-[1.3] text-[var(--color-obsidian)]">
              {t(c.titleKey)}
            </h3>
            <p className="mt-2 text-[13px] leading-[1.5] text-[var(--color-gravel)]">{t(c.blurbKey)}</p>
            <div className="mt-auto flex gap-3 pt-5 text-[12px] font-medium text-[var(--color-obsidian)]">
              <a href={c.tutorial} className="inline-flex items-center gap-1 hover:underline">
                <BookOpen size={12} /> {t("landing.tutorials.tutorial_link")}
              </a>
              <a href={c.code} className="inline-flex items-center gap-1 hover:underline">
                <Github size={12} /> {t("landing.tutorials.code_link")}
              </a>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 flex justify-center">
        <a
          href="#"
          className="inline-flex h-10 items-center gap-2 rounded-full border border-[var(--color-chalk)] bg-white px-5 text-[13px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
        >
          {t("landing.tutorials.see_all")} <ArrowUpRight size={13} />
        </a>
      </div>
    </section>
  );
}

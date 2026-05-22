import { ArrowUpRight, BookOpen, Github } from "lucide-react";

interface Card {
  title: string;
  blurb: string;
  tutorial: string;
  code: string;
  tag: string;
}

const CARDS: Card[] = [
  {
    title: "Who talked about us",
    blurb: "Find every clip a speaker mentions a brand or product.",
    tutorial: "#",
    code: "#",
    tag: "Brand Analytics",
  },
  {
    title: "Generate social media posts",
    blurb: "Auto-summarize a video into TikTok / IG-ready captions and topic tags.",
    tutorial: "#",
    code: "#",
    tag: "Content",
  },
  {
    title: "Shade finder",
    blurb: "Detect every lipstick swatch across an unboxing reel.",
    tutorial: "#",
    code: "#",
    tag: "E-Commerce",
  },
  {
    title: "Interview analyzer",
    blurb: "Chapter long-form interviews and pull stand-out quotes automatically.",
    tutorial: "#",
    code: "#",
    tag: "Media",
  },
];

export function Tutorials() {
  return (
    <section id="tutorials" className="mx-auto max-w-[1200px] px-6 py-24">
      <header className="mb-12 text-center">
        <h2 className="mx-auto max-w-[720px] text-[40px] font-light leading-[1.08] tracking-[-1px] text-[var(--color-obsidian)] md:text-[48px]">
          Take the reins with our quick-start tutorials.
        </h2>
        <p className="mx-auto mt-5 max-w-[560px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          Production-ready recipes — clone the repo, ingest a few videos, ship a feature this
          afternoon.
        </p>
      </header>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map((c) => (
          <div
            key={c.title}
            className="flex flex-col rounded-[20px] border border-[var(--color-chalk)] bg-white p-5 transition-all hover:shadow-hairline"
          >
            <span className="self-start rounded-md bg-[var(--color-powder)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--color-gravel)]">
              {c.tag}
            </span>
            <h3 className="mt-4 text-[16px] font-medium leading-[1.3] text-[var(--color-obsidian)]">
              {c.title}
            </h3>
            <p className="mt-2 text-[13px] leading-[1.5] text-[var(--color-gravel)]">{c.blurb}</p>
            <div className="mt-auto flex gap-3 pt-5 text-[12px] font-medium text-[var(--color-obsidian)]">
              <a href={c.tutorial} className="inline-flex items-center gap-1 hover:underline">
                <BookOpen size={12} /> Tutorial
              </a>
              <a href={c.code} className="inline-flex items-center gap-1 hover:underline">
                <Github size={12} /> Code
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
          See all tutorials <ArrowUpRight size={13} />
        </a>
      </div>
    </section>
  );
}

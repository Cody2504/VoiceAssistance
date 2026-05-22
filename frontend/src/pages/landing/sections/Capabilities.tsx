import { Link } from "react-router";
import { SearchIcon, AnalyzeIcon, EmbedIcon } from "@/components/brand/FeatureIcon";
import { cn } from "@/lib/utils";

interface PanelData {
  to: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  image: string;
  imageAlt: string;
  panelClass: string;
  titleClass: string;
}

const PANELS: PanelData[] = [
  {
    to: "/playground/search",
    icon: <SearchIcon size={32} />,
    title: "Search",
    body: "Find specific moments within your videos by describing the scene in natural language.",
    image: "/twelvelabs/search.png",
    imageAlt: "Search illustration",
    panelClass: "bg-[#fbdfff]",
    titleClass: "text-[#5e3b66]",
  },
  {
    to: "/playground/analyze",
    icon: <AnalyzeIcon size={32} />,
    title: "Analyze",
    body: "Generate text from videos — summary, chapters, highlights and more.",
    image: "/twelvelabs/analyze.png",
    imageAlt: "Analyze illustration",
    panelClass: "bg-[#fde3a2]",
    titleClass: "text-[#7d5d0c]",
  },
  {
    to: "/playground/segment",
    icon: <EmbedIcon size={32} />,
    title: "Segment",
    body: "Partition videos into labeled, time-stamped chapters you can reuse downstream.",
    image: "/twelvelabs/embed.png",
    imageAlt: "Segment illustration",
    panelClass: "bg-[#c4eefe]",
    titleClass: "text-[#26586d]",
  },
];

export function Capabilities() {
  return (
    <section id="capabilities" className="mx-auto max-w-[1200px] px-6 pb-28">
      <header className="mb-12 text-center">
        <h2 className="text-[40px] font-light leading-[1.05] tracking-[-1px] text-[var(--color-obsidian)] md:text-[52px]">
          Human-level understanding.
          <br />
          For superhuman feats.
        </h2>
        <p className="mx-auto mt-6 max-w-[620px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          Experience semantic search and video-to-text capabilities that surpass anything you've
          tried before — video-native AI makes all the difference.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-3">
        {PANELS.map((p) => (
          <Link key={p.title} to={p.to} className="group flex flex-col items-center text-center">
            <div className="mb-3 inline-flex items-center gap-2">
              {p.icon}
              <span className={cn("text-[22px] font-medium tracking-[-0.2px]", p.titleClass)}>
                {p.title}
              </span>
            </div>
            <p className="mb-5 max-w-[320px] text-[14px] leading-[1.5] text-[var(--color-gravel)]">
              {p.body}
            </p>
            <div
              className={cn(
                "flex aspect-[16/9] w-full items-center justify-center overflow-hidden rounded-[34px] p-6 transition-all duration-200 ease-out group-hover:rounded-[40px] group-hover:shadow-hairline",
                p.panelClass,
              )}
            >
              <img src={p.image} alt={p.imageAlt} className="h-full w-full object-contain" loading="lazy" />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

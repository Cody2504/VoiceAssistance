import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import {
  Upload,
  ArrowRight,
  Info,
  X,
  Play,
  ChevronRight,
} from "lucide-react";
import { PillButton } from "@/components/ui/PillButton";
import { SearchIcon, AnalyzeIcon, EmbedIcon } from "@/components/brand/FeatureIcon";
import { uploadVideo } from "@/apis/videos.api";
import { useVideosQuery, qk } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

interface FeaturePanelData {
  to: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  image: string;
  imageAlt: string;
  panelClass: string;
  titleClass: string;
}

const FEATURES: FeaturePanelData[] = [
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

const QUICKSTART_SNIPPET = `from tl_jockey import Client

client = Client(api_key="<YOUR_API_KEY>")

index = client.indexes.create(
    name="<YOUR_INDEX_NAME>",
    models=[{"name": "viclip", "modality": "video"}],
)

print(f"Created index: id={index.id}")`;

function FeaturePanel({ data }: { data: FeaturePanelData }) {
  return (
    <Link
      to={data.to}
      className="group flex flex-col items-center text-center"
    >
      <div className="mb-3 inline-flex items-center gap-2">
        {data.icon}
        <span className={cn("text-[22px] font-medium tracking-[-0.2px]", data.titleClass)}>
          {data.title}
        </span>
      </div>
      <p className="mb-5 max-w-[320px] text-[14px] leading-[1.5] text-[var(--color-gravel)]">
        {data.body}
      </p>
      <div
        className={cn(
          "flex aspect-[16/9] w-full items-center justify-center overflow-hidden rounded-[34px] p-6 transition-all duration-200 ease-out group-hover:rounded-[40px] group-hover:shadow-hairline",
          data.panelClass,
        )}
      >
        <img
          src={data.image}
          alt={data.imageAlt}
          className="h-full w-full object-contain"
          loading="lazy"
        />
      </div>
    </Link>
  );
}

function IndexPreviewCard({
  title,
  caption,
  videoCount,
  durationLabel,
  variant = "empty",
}: {
  title: string;
  caption: string;
  videoCount: number;
  durationLabel: string;
  variant?: "empty" | "sample-mix" | "sample-ads" | "sample-edu";
}) {
  const variantClass = {
    empty: "bg-gradient-warm",
    "sample-mix": "bg-gradient-to-br from-amber-100 via-orange-100 to-emerald-100",
    "sample-ads": "bg-gradient-to-br from-rose-100 via-pink-100 to-violet-100",
    "sample-edu": "bg-gradient-to-br from-sky-100 via-cyan-100 to-emerald-100",
  }[variant];

  return (
    <div className="group">
      <div
        className={cn(
          "relative h-[170px] overflow-hidden border border-[var(--color-chalk)] transition-all duration-200 ease-out",
          "rounded-[16px] group-hover:rounded-[22px] group-hover:shadow-hairline",
          variantClass,
        )}
      >
        <div className="absolute bottom-3 left-3 inline-flex items-center gap-2 rounded-md bg-black/55 px-2 py-1 text-[11px] text-white">
          <Play size={11} fill="currentColor" />
          {videoCount} {videoCount === 1 ? "Video" : "Videos"} ({durationLabel})
        </div>
      </div>
      <h4 className="mt-3 text-[15px] font-medium text-[var(--color-obsidian)]">{title}</h4>
      <p className="mt-0.5 text-[12px] text-[var(--color-gravel)]">{caption}</p>
    </div>
  );
}

function fmtDuration(totalSec: number): string {
  if (totalSec < 60) return `${Math.round(totalSec)}s`;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function Overview() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: videos = [] } = useVideosQuery();
  const [bannerVisible, setBannerVisible] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const totalDuration = videos.reduce((sum, v) => sum + (v.duration_s ?? 0), 0);

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const f of Array.from(files)) {
        await uploadVideo(f);
      }
      await qc.invalidateQueries({ queryKey: qk.videos(user?.id) });
    } catch (e) {
      console.error("upload failed", e);
    } finally {
      setUploading(false);
    }
  }, []);

  return (
    <div className="mx-auto max-w-[1200px] px-8 py-8">
      {bannerVisible && (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-[#f7e0a3] bg-[#fdf5d6] px-4 py-2.5 text-[13px] text-[#5a4500]">
          <Info size={15} className="shrink-0" />
          <span className="flex-1">
            Welcome back. Drop your videos to start indexing —{" "}
            <a href="#" className="underline underline-offset-2">
              read the docs
            </a>{" "}
            for ingest options.
          </span>
          <button
            onClick={() => setBannerVisible(false)}
            className="rounded p-1 text-[#5a4500]/70 hover:bg-[#f5deb0]"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <section className="mb-4 text-center">
        <h1 className="text-[42px] font-light leading-[1.05] tracking-[-1.2px] text-[var(--color-obsidian)]">
          Human-level understanding.
          <br />
          For superhuman feats.
        </h1>
        <p className="mx-auto mt-5 max-w-[620px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          Experience semantic search and video-to-text capabilities that surpass anything you've tried
          before — video-native AI makes all the difference.
        </p>
      </section>

      <section className="mb-12 grid gap-6 md:grid-cols-3">
        {FEATURES.map((f) => (
          <FeaturePanel key={f.title} data={f} />
        ))}
      </section>

      <h2 className="mb-4 text-[28px] font-light tracking-[-0.56px] text-[var(--color-obsidian)]">
        Take the next step
      </h2>

      <div className="mb-10 grid grid-cols-1 gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          className={cn(
            "relative flex flex-col items-center justify-center rounded-[18px] border border-dashed border-[var(--color-chalk)] bg-gradient-warm px-8 py-12 transition-colors",
            dragOver && "border-[var(--color-obsidian)]",
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="grid h-12 w-12 place-items-center rounded-full bg-white shadow-hairline hover:bg-[var(--color-powder)]"
          >
            <Upload size={18} className="text-[var(--color-obsidian)]" />
          </button>
          <p className="mt-4 text-[16px] font-medium text-[var(--color-obsidian)]">
            {uploading ? "Uploading…" : "Drop videos or browse files"}
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-[11px] text-[var(--color-gravel)]">
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              Duration 4sec–1hr
            </span>
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              Resolution 360p–4k
            </span>
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              Ratio 1:1–1:2.4
            </span>
            <span className="rounded-md border border-[var(--color-chalk)] bg-white/60 px-2 py-0.5">
              File size ≤2GB per video
            </span>
          </div>
          <p className="mt-3 text-[11px] text-[var(--color-slate)]">
            *To upload longer videos, create an index with the corpus model.
          </p>
        </div>

        <div className="rounded-[18px] border border-[var(--color-chalk)] bg-white p-5 shadow-hairline">
          <h3 className="text-[18px] font-medium text-[var(--color-obsidian)]">API Quickstart</h3>
          <p className="mt-1 text-[13px] text-[var(--color-gravel)]">
            Make your first API request in minutes.
          </p>
          <pre className="mt-4 max-h-[160px] overflow-auto rounded-[10px] bg-[#0a0a0a] p-3 text-[11px] leading-[1.6] text-[#d6d3cd]">
            <code className="font-mono">{QUICKSTART_SNIPPET}</code>
          </pre>
        </div>
      </div>

      <div className="mb-5 flex items-end justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-[28px] font-light tracking-[-0.56px] text-[var(--color-obsidian)]">
              My indexes
            </h2>
            <Info size={14} className="text-[var(--color-slate)]" />
          </div>
          <Link
            to="/indexes"
            className="mt-1 inline-flex items-center gap-1 text-[13px] text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]"
          >
            See full list <ChevronRight size={13} />
          </Link>
        </div>
        <PillButton
          variant="ghost"
          rightIcon={<ArrowRight size={14} />}
          onClick={() => navigate("/indexes")}
        >
          Create Index
        </PillButton>
      </div>

      <div className="mb-4 flex items-center gap-3 rounded-xl border border-[#bce5b6] bg-[#dff5d8] px-4 py-2.5 text-[12px] text-[#1e5a23]">
        <Info size={14} className="shrink-0" />
        You are currently on the Free Plan, which means that your index will expire 90 days after it was created.
        <button className="ml-auto text-[#1e5a23]/60 hover:text-[#1e5a23]">
          <X size={13} />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-5 pb-12 sm:grid-cols-2 lg:grid-cols-3">
        <Link to="/indexes" className="contents">
          <IndexPreviewCard
            title="My Index (Default)"
            caption={`Created on ${new Date().toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })}`}
            videoCount={videos.length}
            durationLabel={videos.length ? fmtDuration(totalDuration) : "0s"}
            variant="empty"
          />
        </Link>
        <IndexPreviewCard
          title="Sample Index: Mix"
          caption="Sample · 161 Videos (8h 35m)"
          videoCount={161}
          durationLabel="8h 35m"
          variant="sample-mix"
        />
        <IndexPreviewCard
          title="Sample Index: Ads"
          caption="Sample · 27 Videos (47m 7s)"
          videoCount={27}
          durationLabel="47m 7s"
          variant="sample-ads"
        />
        <IndexPreviewCard
          title="Sample Index: E Learning"
          caption="Sample · 24 Videos (2h 41m)"
          videoCount={24}
          durationLabel="2h 41m"
          variant="sample-edu"
        />
        <IndexPreviewCard
          title="Sample Index: Social Media"
          caption="Sample · 15 Videos (2h 17m)"
          videoCount={15}
          durationLabel="2h 17m"
          variant="sample-mix"
        />
        <IndexPreviewCard
          title="Sample Index: Sports"
          caption="Sample · 19 Videos (2h 15m)"
          videoCount={19}
          durationLabel="2h 15m"
          variant="sample-ads"
        />
      </div>
    </div>
  );
}

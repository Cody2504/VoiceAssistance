import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";

import { Card } from "@/components/ui/card";
import {
  getSimilarVideos,
  type SimilarVideosResponse,
  type VideoSummary,
} from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel, type ExampleTile } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { VideoPicker } from "./components/VideoPicker";

const EXAMPLES: ExampleTile<{ note: string }>[] = [
  { id: "topic-similarity", title: "Find videos with similar topics", tags: ["Recommend", "Content"], preset: { note: "Pick any seed video; results are ranked by mean-pooled caption-embedding cosine in your library." } },
  { id: "library-explore", title: "Explore your own library", tags: ["Recommend", "Discovery"], preset: { note: "Best used after you've uploaded 3+ videos of varied topics." } },
];

export default function Recommend() {
  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SimilarVideosResponse | null>(null);
  const [note, setNote] = useState("");

  const run = async () => {
    if (!video) return;
    setRunning(true);
    try {
      const r = await getSimilarVideos(video.id, 5);
      setResult(r);
      if (r.results.length === 0) toast.info(r.reason || "No similar videos yet — upload more to your library.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Recommendation failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PlaygroundShell
      title="Recommend"
      subtitle="Find videos in your library most similar to a seed video."
      formPanel={
        <FormPanel
          runLabel="Recommend"
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint="Cosine similarity over mean-pooled caption embeddings. No new model required."
        >
          <Field label="seed_video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>
          {note && (
            <p className="rounded-md bg-neutral-50 p-3 text-[11px] text-neutral-600">{note}</p>
          )}
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<{ note: string }>
          kind="search"
          examples={EXAMPLES}
          onSelect={(p) => setNote(p.note)}
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title="Similar videos"
            counter={`${result.results.length} result${result.results.length === 1 ? "" : "s"}`}
          >
            {result.results.length === 0 ? (
              <p className="text-sm text-neutral-500">
                {result.reason ?? "No similar videos in your library yet. Upload more videos in Library."}
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {result.results.map((r) => (
                  <Link key={r.video_id} to={`/video/${r.video_id}`} className="block">
                    <Card className="flex h-full flex-col gap-2 p-4 transition-colors hover:border-neutral-400">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-sm font-medium text-neutral-900" title={r.original_filename}>
                          {r.original_filename || "(untitled)"}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-neutral-500">
                          score={r.score.toFixed(3)}
                        </span>
                      </div>
                      <div className="text-[11px] text-neutral-500">
                        {r.duration_s != null ? formatSeconds(r.duration_s) : "—"} · {r.shot_count ?? 0} shots
                      </div>
                      <div className="mt-auto inline-flex items-center gap-1 text-[11px] text-neutral-500">
                        View <ArrowRight className="h-3 w-3" />
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </ResultsPanel>
        )
      }
    />
  );
}

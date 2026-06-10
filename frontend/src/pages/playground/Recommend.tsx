import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";

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

export default function Recommend() {
  const { t } = useTranslation();

  const EXAMPLES: ExampleTile<{ note: string }>[] = [
    { id: "topic-similarity", title: t("playground.recommend.example_topic_title"),   tags: ["Recommend", "Content"],   preset: { note: t("playground.recommend.example_topic_note") } },
    { id: "library-explore",  title: t("playground.recommend.example_library_title"), tags: ["Recommend", "Discovery"], preset: { note: t("playground.recommend.example_library_note") } },
  ];

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
      if (r.results.length === 0) toast.info(r.reason || t("playground.recommend.no_similar_toast"));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t("playground.recommend.error");
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PlaygroundShell
      title={t("playground.recommend.title")}
      subtitle={t("playground.recommend.subtitle")}
      formPanel={
        <FormPanel
          runLabel={t("playground.recommend.title")}
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint={t("playground.recommend.hint")}
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
            title={t("playground.recommend.results_title")}
            counter={`${result.results.length} result${result.results.length === 1 ? "" : "s"}`}
          >
            {result.results.length === 0 ? (
              <p className="text-sm text-neutral-500">
                {result.reason ?? t("playground.recommend.no_similar")}
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
                        {r.duration_s != null ? formatSeconds(r.duration_s) : "—"} · {r.shot_count ?? 0} {t("playground.recommend.shots")}
                      </div>
                      <div className="mt-auto inline-flex items-center gap-1 text-[11px] text-neutral-500">
                        {t("playground.recommend.view")} <ArrowRight className="h-3 w-3" />
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

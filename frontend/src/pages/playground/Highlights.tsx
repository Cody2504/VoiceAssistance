import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { GroundingTimeline } from "@/components/video/GroundingTimeline";
import { VideoPlayer, type VideoPlayerHandle } from "@/components/video/VideoPlayer";
import {
  getHighlights,
  getStreamUrl,
  type HighlightsResponse,
  type VideoSummary,
} from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel, type ExampleTile } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { VideoPicker } from "./components/VideoPicker";

export default function Highlights() {
  const { t } = useTranslation();

  const EXAMPLES: ExampleTile<{ note: string }>[] = [
    { id: "auto-reel", title: t("playground.highlights.example_auto_reel_title"), tags: ["Highlights", "Sports"], preset: { note: t("playground.highlights.example_auto_reel_note") } },
    { id: "trailer",   title: t("playground.highlights.example_trailer_title"),   tags: ["Highlights", "Media"],  preset: { note: t("playground.highlights.example_trailer_note") } },
  ];

  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<HighlightsResponse | null>(null);
  const [streamUrl, setStreamUrl] = useState<string>("");
  const [note, setNote] = useState("");
  const player = useRef<VideoPlayerHandle>(null);

  useEffect(() => {
    if (!video) { setStreamUrl(""); return; }
    let alive = true;
    getStreamUrl(video.id)
      .then((u) => { if (alive) setStreamUrl(u); })
      .catch(() => setStreamUrl(""));
    return () => { alive = false; };
  }, [video?.id]);

  const run = async () => {
    if (!video) return;
    setRunning(true);
    try {
      const r = await getHighlights(video.id, 10);
      setResult(r);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t("playground.highlights.error");
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const seek = (time: number) => player.current?.seekTo(time);

  return (
    <PlaygroundShell
      title={t("playground.highlights.title")}
      subtitle={t("playground.highlights.subtitle")}
      formPanel={
        <FormPanel
          runLabel={t("playground.highlights.run_label")}
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint={t("playground.highlights.hint")}
        >
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>
          {note && (
            <p className="rounded-md bg-neutral-50 p-3 text-[11px] text-neutral-600">{note}</p>
          )}
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<{ note: string }>
          kind="analyze"
          examples={EXAMPLES}
          onSelect={(p) => setNote(p.note)}
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title={t("playground.highlights.results_title")}
            counter={`${result.moments.length} span${result.moments.length === 1 ? "" : "s"} · ${result.shots?.length ?? 0} ranked shots`}
          >
            <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
              <div className="space-y-3">
                {streamUrl && <VideoPlayer ref={player} src={streamUrl} />}
                <GroundingTimeline
                  duration={video?.duration_s ?? 0}
                  result={{ video_id: result.video_id, query: result.query_used, shots: result.shots, spans: result.moments }}
                  onSeek={seek}
                />
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                  {t("playground.highlights.moment_spans")}
                </h3>
                {result.moments.length === 0 ? (
                  <p className="text-xs text-neutral-500">{t("playground.highlights.no_spans")}</p>
                ) : (
                  <ul className="max-h-[360px] space-y-1 overflow-y-auto pr-2">
                    {result.moments.map((m, i) => (
                      <li key={`${m.t_start}-${i}`}>
                        <button
                          type="button"
                          onClick={() => seek(m.t_start)}
                          className="w-full rounded border border-neutral-100 bg-white p-2 text-left text-xs transition hover:border-neutral-300 hover:bg-neutral-50"
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="font-mono text-[11px] text-neutral-800">
                              {formatSeconds(m.t_start)}–{formatSeconds(m.t_end)}
                            </span>
                            <span className="font-mono text-[10px] text-neutral-500">
                              score={m.score.toFixed(3)}
                            </span>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </ResultsPanel>
        )
      }
    />
  );
}

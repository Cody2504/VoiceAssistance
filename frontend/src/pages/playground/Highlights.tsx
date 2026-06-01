import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

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

const EXAMPLES: ExampleTile<{ note: string }>[] = [
  { id: "auto-reel", title: "Auto-pick top moments for a highlight reel", tags: ["Highlights", "Sports"], preset: { note: "QD-DETR saliency picks the most interesting clips with no query needed." } },
  { id: "trailer", title: "Generate trailer-style cuts", tags: ["Highlights", "Media"], preset: { note: "Top 10 saliency peaks. Use the moment spans below to cut a reel." } },
];

export default function Highlights() {
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
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Highlights failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const seek = (t: number) => player.current?.seekTo(t);

  return (
    <PlaygroundShell
      title="Highlights"
      subtitle="Auto-pick the top moments — no query required."
      formPanel={
        <FormPanel
          runLabel="Find highlights"
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint="Runs the QD-DETR saliency head with a generic 'key moment' prompt. Top-10 spans returned."
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
            title="Top moments"
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
                  Moment spans (high → low)
                </h3>
                {result.moments.length === 0 ? (
                  <p className="text-xs text-neutral-500">No spans returned.</p>
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

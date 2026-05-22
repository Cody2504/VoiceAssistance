import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { GroundingTimeline } from "@/components/video/GroundingTimeline";
import { VideoPlayer, type VideoPlayerHandle } from "@/components/video/VideoPlayer";
import {
  getStreamUrl,
  groundVideo,
  type GroundResponse,
  type VideoSummary,
} from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { VideoPicker } from "./components/VideoPicker";
import { GROUND_EXAMPLES, type GroundPreset } from "./data/examples";

export default function Ground() {
  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<GroundResponse | null>(null);
  const [streamUrl, setStreamUrl] = useState<string>("");
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
    if (!video || !query.trim()) return;
    setRunning(true);
    try {
      const r = await groundVideo(video.id, query.trim());
      setResult(r);
      if (r.shots.length === 0) toast.info("No matching moments found");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Ground failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const canRun = !!video && query.trim().length > 0 && !running;
  const seek = (t: number) => player.current?.seekTo(t);

  return (
    <PlaygroundShell
      title="Ground"
      subtitle="Locate the exact moment in a video that matches your text query."
      formPanel={
        <FormPanel
          runLabel="Ground"
          onRun={run}
          running={running}
          canRun={canRun}
          hint="Uses the trained QD-DETR head. Returns ranked shot candidates plus a predicted (start, end) span."
        >
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>

          <Field label="query_text" required>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Describe the moment you're looking for"
              className="min-h-[88px] w-full resize-none rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm focus:border-neutral-400 focus:outline-none"
            />
          </Field>
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<GroundPreset>
          examples={GROUND_EXAMPLES}
          onSelect={(preset) => setQuery(preset.query)}
          kind="search"
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title={`Moment grounding — "${result.query}"`}
            counter={`${result.shots.length} shot${result.shots.length === 1 ? "" : "s"} · ${result.spans.length} span${result.spans.length === 1 ? "" : "s"}`}
          >
            <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
              <div className="space-y-3">
                {streamUrl && <VideoPlayer ref={player} src={streamUrl} />}
                <GroundingTimeline
                  duration={video?.duration_s ?? 0}
                  result={result}
                  onSeek={seek}
                />
              </div>

              <div className="space-y-1.5">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                  Ranked shots
                </h3>
                {result.shots.length === 0 ? (
                  <p className="text-xs text-neutral-500">No shots matched.</p>
                ) : (
                  <ul className="max-h-[360px] space-y-1 overflow-y-auto pr-2">
                    {result.shots.map((s) => (
                      <li key={s.idx}>
                        <button
                          type="button"
                          onClick={() => seek(s.t_start)}
                          className="w-full rounded border border-neutral-100 bg-white p-2 text-left text-xs transition hover:border-neutral-300 hover:bg-neutral-50"
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="font-mono text-[11px] text-neutral-700">
                              {formatSeconds(s.t_start)}–{formatSeconds(s.t_end)}
                            </span>
                            <span className="font-mono text-[10px] text-neutral-500">
                              rel={(s.relevance ?? 0).toFixed(2)}
                            </span>
                          </div>
                          {s.asr_text && (
                            <p className="mt-1 line-clamp-2 text-[11px] text-neutral-500">
                              {s.asr_text}
                            </p>
                          )}
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

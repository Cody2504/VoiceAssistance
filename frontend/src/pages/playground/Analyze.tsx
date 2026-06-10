import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui/input";
import { VideoPlayer, type VideoPlayerHandle } from "@/components/video/VideoPlayer";
import {
  askVideo,
  getStreamUrl,
  tileSupportsModality,
  type AnalyzeResponse,
  type VideoSummary,
} from "@/apis/videos.api";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { AdvancedSettings } from "./components/AdvancedSettings";
import { VideoPicker } from "./components/VideoPicker";
import { ANALYZE_EXAMPLES, type AnalyzePreset } from "./data/examples";

interface FormState extends AnalyzePreset {
  // video is selected separately via VideoPicker
}

const DEFAULT_FORM: FormState = { prompt: "", use_range: false };

export default function Analyze() {
  const { t } = useTranslation();
  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [streamUrl, setStreamUrl] = useState<string>("");
  const supported = tileSupportsModality("analyze", video?.modality ?? null);
  const player = useRef<VideoPlayerHandle>(null);

  useEffect(() => {
    if (!video) { setStreamUrl(""); return; }
    let alive = true;
    getStreamUrl(video.id)
      .then((u) => { if (alive) setStreamUrl(u); })
      .catch(() => setStreamUrl(""));
    return () => { alive = false; };
  }, [video?.id]);

  const seek = (time: number) => player.current?.seekTo(time);

  const run = async () => {
    if (!video || !form.prompt.trim()) return;
    setRunning(true);
    try {
      const r = await askVideo(
        video.id,
        form.prompt.trim(),
        form.use_range ? form.t_start : undefined,
        form.use_range ? form.t_end : undefined,
      );
      setResult(r);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t("playground.analyze.error");
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const canRun = !!video && supported && form.prompt.trim().length > 0 && !running;

  return (
    <PlaygroundShell
      title={t("playground.analyze.title")}
      subtitle={t("playground.analyze.subtitle")}
      formPanel={
        <FormPanel runLabel={t("playground.analyze.title")} onRun={run} running={running} canRun={canRun}>
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>

          <Field label="prompt" required hint={`${form.prompt.length}/2048 tokens estimated`}>
            <textarea
              value={form.prompt}
              onChange={(e) => setForm({ ...form, prompt: e.target.value.slice(0, 2048) })}
              placeholder={t("playground.analyze.placeholder")}
              className="min-h-[140px] w-full resize-none rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm focus:border-neutral-400 focus:outline-none"
            />
          </Field>

          <AdvancedSettings
            onReset={() => setForm({ ...form, use_range: false, t_start: undefined, t_end: undefined })}
          >
            <label className="flex items-center gap-2 text-xs text-neutral-700">
              <input
                type="checkbox"
                checked={form.use_range}
                onChange={(e) => setForm({ ...form, use_range: e.target.checked })}
                className="h-3.5 w-3.5"
              />
              {t("playground.analyze.restrict_range")}
            </label>

            {form.use_range && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="t_start" hint={t("playground.analyze.hint_seconds")}>
                  <Input
                    type="number"
                    min={0}
                    step={0.1}
                    value={form.t_start ?? 0}
                    onChange={(e) => setForm({ ...form, t_start: Number(e.target.value) })}
                  />
                </Field>
                <Field label="t_end" hint={t("playground.analyze.hint_seconds")}>
                  <Input
                    type="number"
                    min={0}
                    step={0.1}
                    value={form.t_end ?? 30}
                    onChange={(e) => setForm({ ...form, t_end: Number(e.target.value) })}
                  />
                </Field>
              </div>
            )}
          </AdvancedSettings>
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<AnalyzePreset>
          examples={ANALYZE_EXAMPLES}
          onSelect={(preset) => setForm({ ...form, ...preset })}
          kind="analyze"
        />
      }
      resultsPanel={
        <>
          {video && !supported && (
            <div className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {t("playground.analyze.unsupported", { modality: video.modality })}
            </div>
          )}
          {result && (
            <ResultsPanel
              title={t("playground.analyze.result_title")}
              counter={`prompt: "${truncate(result.question, 80)}" · used ${result.used_windows} windows, ${result.used_segments} segments`}
            >
              <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
                <div className="space-y-3">
                  {streamUrl && <VideoPlayer ref={player} src={streamUrl} />}
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-800">
                    {result.answer}
                  </pre>
                </div>

                <div className="space-y-1.5">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                    {t("playground.analyze.citations")}
                  </h3>
                  {result.citations.length === 0 ? (
                    <p className="text-xs text-neutral-500">{t("playground.analyze.no_citations")}</p>
                  ) : (
                    <ul className="max-h-[360px] space-y-1 overflow-y-auto pr-2">
                      {result.citations.map((c, i) => (
                        <li key={i}>
                          <button
                            type="button"
                            onClick={() => seek(c.t_start)}
                            className="w-full rounded border border-neutral-100 bg-white p-2 text-left text-xs transition hover:border-neutral-300 hover:bg-neutral-50"
                          >
                            <div className="flex items-baseline justify-between gap-2">
                              <span className="font-mono text-[11px] text-neutral-700">
                                {formatTime(c.t_start)}–{formatTime(c.t_end)}
                              </span>
                              <span className="font-mono text-[10px] text-neutral-500">
                                seg {c.segment_idx}
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
          )}
        </>
      }
    />
  );
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function formatTime(t: number) {
  const s = Math.max(0, Math.round(t));
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}

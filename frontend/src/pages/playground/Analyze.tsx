import { useState } from "react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { askVideo, type VideoSummary } from "@/apis/videos.api";

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

interface AnalyzeResult {
  video_id: string;
  question: string;
  answer: string;
}

export default function Analyze() {
  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);

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
        "Analyze failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const canRun = !!video && form.prompt.trim().length > 0 && !running;

  return (
    <PlaygroundShell
      title="Analyze"
      subtitle="Generate summaries, chapters, highlights, and more insights."
      formPanel={
        <FormPanel runLabel="Analyze" onRun={run} running={running} canRun={canRun}>
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>

          <Field label="prompt" required hint={`${form.prompt.length}/2048 tokens estimated`}>
            <textarea
              value={form.prompt}
              onChange={(e) => setForm({ ...form, prompt: e.target.value.slice(0, 2048) })}
              placeholder="Type in a prompt or select a suggested prompt. e.g., Summarize the video and provide timecodes"
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
              Restrict to a specific time range
            </label>

            {form.use_range && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="t_start" hint="seconds">
                  <Input
                    type="number"
                    min={0}
                    step={0.1}
                    value={form.t_start ?? 0}
                    onChange={(e) => setForm({ ...form, t_start: Number(e.target.value) })}
                  />
                </Field>
                <Field label="t_end" hint="seconds">
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
        result && (
          <ResultsPanel title="Answer" counter={`prompt: "${truncate(result.question, 80)}"`}>
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-800">
              {result.answer}
            </pre>
          </ResultsPanel>
        )
      }
    />
  );
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

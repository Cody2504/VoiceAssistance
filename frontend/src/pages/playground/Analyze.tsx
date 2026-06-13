import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";
import { Check, Copy, Sparkles } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  askVideo,
  listVideos,
  tileSupportsModality,
  type AnalyzeResponse,
  type VideoSummary,
} from "@/apis/videos.api";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel } from "./components/ExamplesPanel";
import { AdvancedSettings } from "./components/AdvancedSettings";
import { VideoPicker } from "./components/VideoPicker";
import { cn } from "@/lib/utils";
import { ANALYZE_EXAMPLES, type AnalyzePreset } from "./data/examples";

interface FormState extends AnalyzePreset {
  // video is selected separately via VideoPicker
}

const DEFAULT_FORM: FormState = { prompt: "", use_range: false };

export default function Analyze() {
  const { t } = useTranslation();
  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [searchParams] = useSearchParams();

  // Deep-link support: /playground/analyze?video_id=<id> auto-selects the video
  // (used by the index-detail Analyze buttons). index_id is accepted but unused.
  useEffect(() => {
    const vid = searchParams.get("video_id");
    if (!vid) return;
    listVideos()
      .then((vs) => {
        const found = vs.find((v) => v.id === vid);
        if (found) setVideo(found);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [view, setView] = useState<"visual" | "json">("visual");
  const [generatedAt, setGeneratedAt] = useState<string>("");
  const [copied, setCopied] = useState(false);
  const supported = tileSupportsModality("analyze", video?.modality ?? null);

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
      setView("visual");
      setGeneratedAt(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
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
      browsePanel={
        result ? (
          <div className="flex h-full flex-col">
            {/* header — Visual/JSON toggle + status */}
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-8 overflow-hidden rounded-[9.6px] border border-[var(--color-obsidian)]">
                {(["visual", "json"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setView(v)}
                    className={cn(
                      "min-w-[72px] px-3 text-[13px] transition",
                      view === v
                        ? "bg-[var(--color-obsidian)] text-white"
                        : "bg-white text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]",
                    )}
                  >
                    {t(v === "visual" ? "playground.analyze.view_visual" : "playground.analyze.view_json")}
                  </button>
                ))}
              </div>
              <span className="rounded-lg bg-emerald-600 px-2 py-0.5 font-mono text-[12px] font-medium text-white">
                200 OK
              </span>
            </div>

            {/* body */}
            <div className="min-h-[200px] flex-1 overflow-auto rounded-t-[20px] border border-b-0 border-[var(--color-chalk)] bg-white p-5">
              {view === "visual" ? (
                <div className="whitespace-pre-wrap text-[13px] leading-relaxed text-[var(--color-obsidian)]">
                  {result.answer}
                </div>
              ) : (
                <pre className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-[var(--color-obsidian)]">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </div>

            {/* footer — model · time · meta · copy */}
            <div className="flex items-center gap-2 rounded-b-[20px] border border-[var(--color-chalk)] bg-[var(--color-powder)] px-5 py-2 text-[12px]">
              <Sparkles size={15} className="shrink-0 text-[var(--color-gravel)]" />
              <span className="shrink-0 font-semibold text-[var(--color-obsidian)]">
                {t("playground.analyze.model_name")}
              </span>
              {generatedAt && (
                <span className="truncate text-[var(--color-gravel)]">
                  {t("playground.analyze.generated_at", { time: generatedAt })}
                </span>
              )}
              <span className="ml-auto shrink-0 text-[var(--color-gravel)]">
                {t("playground.analyze.meta", {
                  windows: result.used_windows,
                  segments: result.used_segments,
                })}
              </span>
              <button
                type="button"
                aria-label={t("actions.copy")}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(result.answer);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1500);
                  } catch {
                    /* clipboard unavailable — ignore */
                  }
                }}
                className="grid h-7 w-7 shrink-0 place-items-center rounded-[8px] text-[var(--color-obsidian)] transition hover:bg-black/10"
              >
                {copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />}
              </button>
            </div>
          </div>
        ) : video && !supported ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            {t("playground.analyze.unsupported", { modality: video.modality })}
          </div>
        ) : undefined
      }
    />
  );
}

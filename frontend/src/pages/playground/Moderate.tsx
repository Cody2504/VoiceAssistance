import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui/input";
import { getModeration, type ModerateResponse, type VideoSummary } from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel, type ExampleTile } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { VideoPicker } from "./components/VideoPicker";

export default function Moderate() {
  const { t } = useTranslation();

  const EXAMPLES: ExampleTile<{ threshold: number }>[] = [
    { id: "strict",   title: t("playground.moderate.example_strict_title"),   tags: ["Moderate", "Strict"],   preset: { threshold: 0.3 } },
    { id: "standard", title: t("playground.moderate.example_standard_title"), tags: ["Moderate", "Standard"], preset: { threshold: 0.5 } },
    { id: "lenient",  title: t("playground.moderate.example_lenient_title"),  tags: ["Moderate", "Lenient"],  preset: { threshold: 0.8 } },
  ];

  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ModerateResponse | null>(null);

  const run = async () => {
    if (!video) return;
    setRunning(true);
    try {
      setResult(await getModeration(video.id, threshold));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t("playground.moderate.error");
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PlaygroundShell
      title={t("playground.moderate.title")}
      subtitle={t("playground.moderate.subtitle")}
      formPanel={
        <FormPanel
          runLabel={t("playground.moderate.title")}
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint={t("playground.moderate.hint")}
        >
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>
          <Field label="threshold" hint={t("playground.moderate.hint_threshold")}>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={threshold}
              onChange={(e) => setThreshold(Math.max(0, Math.min(1, Number(e.target.value) || 0)))}
            />
          </Field>
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<{ threshold: number }>
          kind="analyze"
          examples={EXAMPLES}
          onSelect={(p) => setThreshold(p.threshold)}
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title={t("playground.moderate.results_title")}
            counter={`${result.flagged_shots.length} flagged · max_nsfw=${result.summary.max_nsfw.toFixed(2)} · max_toxic=${result.summary.max_toxic.toFixed(2)}`}
          >
            {result.flagged_shots.length === 0 ? (
              <p className="text-sm text-emerald-700">
                {t("playground.moderate.no_flags", {
                  threshold: result.threshold.toFixed(2),
                  nsfw: result.summary.max_nsfw.toFixed(3),
                  toxic: result.summary.max_toxic.toFixed(3),
                })}
              </p>
            ) : (
              <ul className="space-y-1">
                {result.flagged_shots.map((s) => (
                  <li key={s.idx} className="rounded border border-rose-200 bg-rose-50 p-2 text-xs">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-mono text-[11px] text-neutral-800">
                        #{s.idx} · {formatSeconds(s.t_start)}–{formatSeconds(s.t_end)}
                      </span>
                      <span className="font-mono text-[10px] text-rose-700">
                        NSFW={s.nsfw_score.toFixed(2)} · Toxic={s.toxic_score.toFixed(2)}
                      </span>
                    </div>
                    {s.asr_text && (
                      <p className="mt-1 line-clamp-2 text-[11px] text-neutral-600">{s.asr_text}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </ResultsPanel>
        )
      }
    />
  );
}

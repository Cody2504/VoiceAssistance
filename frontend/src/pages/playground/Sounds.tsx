import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui/input";
import { getSounds, type SoundsResponse, type VideoSummary } from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel, type ExampleTile } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { VideoPicker } from "./components/VideoPicker";

export default function Sounds() {
  const { t } = useTranslation();

  const EXAMPLES: ExampleTile<{ tag: string }>[] = [
    { id: "laughter",  title: t("playground.sounds.example_laughter_title"), tags: ["Sounds", "Emotion"],   preset: { tag: "Laughter" } },
    { id: "applause",  title: t("playground.sounds.example_applause_title"), tags: ["Sounds", "Crowd"],     preset: { tag: "Applause" } },
    { id: "music",     title: t("playground.sounds.example_music_title"),    tags: ["Sounds", "Music"],     preset: { tag: "Music" } },
    { id: "speech",    title: t("playground.sounds.example_speech_title"),   tags: ["Sounds", "Dialogue"],  preset: { tag: "Speech" } },
    { id: "vehicle",   title: t("playground.sounds.example_vehicle_title"),  tags: ["Sounds", "Outdoor"],   preset: { tag: "Vehicle" } },
    { id: "alarm",     title: t("playground.sounds.example_alarm_title"),    tags: ["Sounds", "Safety"],    preset: { tag: "Alarm" } },
  ];

  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [tag, setTag] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SoundsResponse | null>(null);

  const run = async () => {
    if (!video) return;
    setRunning(true);
    try {
      setResult(await getSounds(video.id, tag.trim() || undefined));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t("playground.sounds.error");
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PlaygroundShell
      title={t("playground.sounds.title")}
      subtitle={t("playground.sounds.subtitle")}
      formPanel={
        <FormPanel
          runLabel={t("playground.sounds.run_label")}
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint={t("playground.sounds.hint")}
        >
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>
          <Field label="tag" hint={t("playground.sounds.hint_tag")}>
            <Input
              type="text"
              placeholder={t("playground.sounds.tag_placeholder")}
              value={tag}
              onChange={(e) => setTag(e.target.value)}
            />
          </Field>
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<{ tag: string }>
          kind="search"
          examples={EXAMPLES}
          onSelect={(p) => setTag(p.tag)}
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title={result.tag ? t("playground.sounds.tagged_title", { tag: result.tag }) : t("playground.sounds.all_shots_title")}
            counter={`${result.shots.length} shot${result.shots.length === 1 ? "" : "s"}`}
          >
            {result.shots.length === 0 ? (
              <p className="text-sm text-neutral-500">
                {t("playground.sounds.no_matches", { tag: result.tag ? ` "${result.tag}"` : "" })}
              </p>
            ) : (
              <ul className="max-h-[480px] space-y-1 overflow-y-auto pr-2">
                {result.shots.map((s) => (
                  <li key={s.idx} className="rounded border border-neutral-100 bg-white p-2 text-xs">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-mono text-[11px] text-neutral-800">
                        #{s.idx} · {formatSeconds(s.t_start)}–{formatSeconds(s.t_end)}
                      </span>
                    </div>
                    {s.audio_tags && s.audio_tags.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {s.audio_tags.map((audioTag) => (
                          <span
                            key={audioTag.label}
                            className="rounded border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 font-mono text-[10px] text-neutral-700"
                            title={`score=${audioTag.score.toFixed(3)}`}
                          >
                            {audioTag.label} <span className="text-neutral-400">{audioTag.score.toFixed(2)}</span>
                          </span>
                        ))}
                      </div>
                    )}
                    {s.asr_text && (
                      <p className="mt-1 line-clamp-2 text-[11px] text-neutral-500">{s.asr_text}</p>
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

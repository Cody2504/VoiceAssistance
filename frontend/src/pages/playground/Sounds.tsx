import { useState } from "react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { getSounds, type SoundsResponse, type VideoSummary } from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field } from "./components/FormPanel";
import { ExamplesPanel, type ExampleTile } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { VideoPicker } from "./components/VideoPicker";

const EXAMPLES: ExampleTile<{ tag: string }>[] = [
  { id: "laughter",  title: "Find moments with laughter",          tags: ["Sounds", "Emotion"], preset: { tag: "Laughter" } },
  { id: "applause",  title: "Find applause / cheering",            tags: ["Sounds", "Crowd"],   preset: { tag: "Applause" } },
  { id: "music",     title: "Find music in the soundtrack",         tags: ["Sounds", "Music"],   preset: { tag: "Music" } },
  { id: "speech",    title: "Find speech-heavy shots",              tags: ["Sounds", "Dialogue"],preset: { tag: "Speech" } },
  { id: "vehicle",   title: "Detect vehicle / engine noise",        tags: ["Sounds", "Outdoor"], preset: { tag: "Vehicle" } },
  { id: "alarm",     title: "Find alarms or sirens",                tags: ["Sounds", "Safety"],  preset: { tag: "Alarm" } },
];

export default function Sounds() {
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
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Sounds query failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PlaygroundShell
      title="Sounds"
      subtitle="Find shots by audio event — laughter, applause, music, alarms, and 523 more."
      formPanel={
        <FormPanel
          runLabel="Search sounds"
          onRun={run}
          running={running}
          canRun={!!video && !running}
          hint="PANN CNN14 tagged each shot with top-5 AudioSet labels at ingest. Search is a case-insensitive substring match."
        >
          <Field label="video" required>
            <VideoPicker selectedId={video?.id} onSelect={setVideo} />
          </Field>
          <Field label="tag" hint="AudioSet label substring (e.g. Laughter, Music). Leave blank to list all shots.">
            <Input
              type="text"
              placeholder="Laughter"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
            />
          </Field>
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<{ tag: string }>
          examples={EXAMPLES}
          onSelect={(p) => setTag(p.tag)}
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title={result.tag ? `Shots tagged "${result.tag}"` : "All shots — audio tags"}
            counter={`${result.shots.length} shot${result.shots.length === 1 ? "" : "s"}`}
          >
            {result.shots.length === 0 ? (
              <p className="text-sm text-neutral-500">
                No shots match{result.tag ? ` "${result.tag}"` : ""}. Try a different tag, or re-ingest the video if audio tags weren't computed.
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
                        {s.audio_tags.map((t) => (
                          <span
                            key={t.label}
                            className="rounded border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 font-mono text-[10px] text-neutral-700"
                            title={`score=${t.score.toFixed(3)}`}
                          >
                            {t.label} <span className="text-neutral-400">{t.score.toFixed(2)}</span>
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

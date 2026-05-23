import { useState } from "react";
import { toast } from "sonner";
import { Link } from "react-router";
import { ImageIcon, UserCircle2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { searchCorpus, type CorpusSearchResponse, type CorpusShot } from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field, CheckOption } from "./components/FormPanel";
import { ExamplesPanel } from "./components/ExamplesPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { AdvancedSettings } from "./components/AdvancedSettings";
import { IndexPicker } from "./components/IndexPicker";
import { SEARCH_EXAMPLES, type SearchPreset } from "./data/examples";

const DEFAULT_FORM: SearchPreset = { query: "", group_by: "clip", top_n: 10 };

interface SearchOptions {
  visual: boolean;
  audio: boolean;
  transcription: boolean;
}

interface TranscriptionOptions {
  lexical: boolean;
  semantic: boolean;
}

export default function Search() {
  const [form, setForm] = useState<SearchPreset>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CorpusSearchResponse | null>(null);
  const [indexSelection, setIndexSelection] = useState<{ id: string; title: string } | null>(null);
  const [searchOpts, setSearchOpts] = useState<SearchOptions>({ visual: true, audio: true, transcription: true });
  const [transcriptOpts, setTranscriptOpts] = useState<TranscriptionOptions>({ lexical: true, semantic: true });

  const run = async () => {
    if (!form.query.trim()) return;
    setRunning(true);
    try {
      const r = await searchCorpus({
        query: form.query.trim(),
        top_n: form.top_n,
        group_by: form.group_by,
      });
      setResult(r);
      if (r.shots.length === 0) toast.info("No matches found");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Search failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <PlaygroundShell
      title="Search"
      subtitle="Find any moment in your videos."
      formPanel={
        <FormPanel runLabel="Search" onRun={run} running={running} canRun={form.query.trim().length > 0}>
          <Field label="index" required>
            <IndexPicker
              selectedIndexId={indexSelection?.id}
              onSelect={(idx) => setIndexSelection(idx)}
            />
          </Field>

          <Field label="query_text" required type="STRING">
            <div className="rounded-xl p-[2px] gradient-border">
              <div className="rounded-[10px] bg-white px-3 py-2">
                <textarea
                  value={form.query}
                  onChange={(e) => setForm({ ...form, query: e.target.value })}
                  placeholder="Search actions, objects, sounds and logos"
                  className="block min-h-[68px] w-full resize-none border-none bg-transparent text-[13px] leading-6 text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-gravel)]/80"
                />
                <div className="flex items-center gap-x-2 pb-0.5 pt-1">
                  <button
                    type="button"
                    disabled
                    aria-label="Add image"
                    className="grid h-7 w-7 place-items-center rounded-[8px] border border-[var(--color-chalk)] text-[var(--color-gravel)] transition-all hover:rounded-[12px] hover:bg-[var(--color-powder)] disabled:opacity-40"
                  >
                    <ImageIcon size={14} />
                  </button>
                  <button
                    type="button"
                    disabled
                    aria-label="Insert entity"
                    className="inline-flex h-7 items-center gap-1 rounded-[8px] border border-[var(--color-chalk)] px-2 text-[11px] text-[var(--color-gravel)] transition-all hover:rounded-[12px] hover:bg-[var(--color-powder)] disabled:opacity-40"
                  >
                    <UserCircle2 size={12} />
                    @ Entity
                  </button>
                </div>
              </div>
            </div>
          </Field>

          <Field label="search_options" required type="ARRAY">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
              <CheckOption
                label="Visual"
                checked={searchOpts.visual}
                onChange={(v) => setSearchOpts((s) => ({ ...s, visual: v }))}
              />
              <CheckOption
                label="Audio"
                checked={searchOpts.audio}
                onChange={(v) => setSearchOpts((s) => ({ ...s, audio: v }))}
              />
              <CheckOption
                label="Transcription"
                checked={searchOpts.transcription}
                onChange={(v) => setSearchOpts((s) => ({ ...s, transcription: v }))}
              />
            </div>
          </Field>

          {searchOpts.transcription && (
            <Field label="transcription_options" type="ARRAY">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
                <CheckOption
                  label="Lexical"
                  checked={transcriptOpts.lexical}
                  onChange={(v) => setTranscriptOpts((s) => ({ ...s, lexical: v }))}
                />
                <CheckOption
                  label="Semantic"
                  checked={transcriptOpts.semantic}
                  onChange={(v) => setTranscriptOpts((s) => ({ ...s, semantic: v }))}
                />
              </div>
            </Field>
          )}

          <AdvancedSettings onReset={() => setForm({ ...form, top_n: 10, group_by: "clip" })}>
            <Field label="group_by" type="ENUM" hint="`clip` returns shot-level hits; `video` returns one hit per video.">
              <select
                value={form.group_by}
                onChange={(e) => setForm({ ...form, group_by: e.target.value as "clip" | "video" })}
                className="h-9 w-full rounded-lg border border-[var(--color-chalk)] bg-white px-3 text-[13px] focus:outline-none"
              >
                <option value="clip">clip</option>
                <option value="video">video</option>
              </select>
            </Field>
            <Field label="top_n" type="INTEGER" hint="1–50. Max number of hits returned.">
              <Input
                type="number"
                min={1}
                max={50}
                value={form.top_n}
                onChange={(e) => setForm({ ...form, top_n: Math.max(1, Math.min(50, Number(e.target.value) || 10)) })}
              />
            </Field>
          </AdvancedSettings>
        </FormPanel>
      }
      examplesPanel={
        <ExamplesPanel<SearchPreset>
          examples={SEARCH_EXAMPLES}
          onSelect={(preset) => setForm(preset)}
          kind="search"
        />
      }
      resultsPanel={
        result && (
          <ResultsPanel
            title={`Hits for "${result.query}"`}
            counter={`${result.shots.length} result${result.shots.length === 1 ? "" : "s"} · group_by=${result.group_by}`}
          >
            {result.shots.length === 0 ? (
              <p className="text-sm text-neutral-500">
                No matches. Try a different phrasing or upload more videos in{" "}
                <Link className="underline" to="/playground/library">Library</Link>.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {result.shots.map((s) => (
                  <ShotCard key={`${s.video_id}-${s.idx}`} shot={s} />
                ))}
              </div>
            )}
          </ResultsPanel>
        )
      }
    />
  );
}

function ShotCard({ shot }: { shot: CorpusShot }) {
  return (
    <Link
      to={`/video/${shot.video_id}`}
      className="block transition hover:opacity-95"
    >
      <Card className="flex h-full flex-col gap-2 p-3 hover:border-neutral-400">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-xs font-medium text-neutral-900" title={shot.original_filename}>
            {shot.original_filename || "(untitled)"}
          </span>
          <span className="shrink-0 font-mono text-[10px] text-neutral-500">
            score={shot.score?.toFixed(3) ?? "—"}
          </span>
        </div>
        <span className="font-mono text-[11px] text-neutral-500">
          {formatSeconds(shot.t_start)}–{formatSeconds(shot.t_end)}
        </span>
        {shot.asr_text && (
          <p className="line-clamp-2 text-[11px] leading-snug text-neutral-600">
            “{shot.asr_text}”
          </p>
        )}
        {shot.ocr_text && (
          <p className="line-clamp-2 text-[11px] leading-snug text-neutral-500">
            <span className="font-mono text-[9px] uppercase tracking-wider text-violet-600">OCR</span>{" "}
            {shot.ocr_text}
          </p>
        )}
        {shot.audio_tags && shot.audio_tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {shot.audio_tags.slice(0, 3).map((t) => (
              <span
                key={t.label}
                className="rounded border border-neutral-200 bg-neutral-50 px-1 py-0.5 font-mono text-[9px] uppercase tracking-wide text-neutral-600"
                title={`${t.label} · ${t.score.toFixed(3)}`}
              >
                {t.label}
              </span>
            ))}
          </div>
        )}
      </Card>
    </Link>
  );
}

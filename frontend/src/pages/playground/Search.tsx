import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Link, useSearchParams } from "react-router";
import { Captions, ChevronLeft, ImageIcon, SquareArrowOutUpRight, UserCircle2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui/input";
import { searchCorpus, searchCorpusByImage, type CorpusSearchResponse, type CorpusShot } from "@/apis/videos.api";
import { getIndex } from "@/apis/indexes.api";
import { VideoThumb } from "@/components/video/VideoThumb";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import { formatSeconds } from "@/lib/utils";

import { PlaygroundShell } from "./components/PlaygroundShell";
import { FormPanel, Field, CheckOption } from "./components/FormPanel";
import { ExamplesPanel } from "./components/ExamplesPanel";
import { AdvancedSettings } from "./components/AdvancedSettings";
import { IndexPicker } from "./components/IndexPicker";
import { IndexVideoBrowser } from "@/pages/indexes/IndexVideoBrowser";
import { SEARCH_EXAMPLES, type SearchPreset } from "./data/examples";

const DEFAULT_FORM: SearchPreset = { query: "", group_by: "video", top_n: 10 };

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
  const { t } = useTranslation();
  const [form, setForm] = useState<SearchPreset>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CorpusSearchResponse | null>(null);
  const [indexSelection, setIndexSelection] = useState<{ id: string; title: string } | null>(null);
  const [searchParams] = useSearchParams();

  // Deep-link support: /playground/search?index_id=<id> preselects the index
  // (used by the index-detail tab bar).
  useEffect(() => {
    const id = searchParams.get("index_id");
    if (!id) return;
    if (id === "default") {
      // The virtual library index has no backend row.
      setIndexSelection({ id: "default", title: t("console.indexes.default_title") });
      return;
    }
    getIndex(id)
      .then((s) => setIndexSelection({ id: s.id, title: s.title || t("pgkit.index_picker.untitled") }))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [searchOpts, setSearchOpts] = useState<SearchOptions>({ visual: true, audio: true, transcription: true });
  const [transcriptOpts, setTranscriptOpts] = useState<TranscriptionOptions>({ lexical: true, semantic: true });
  // @Entity: an attached image used as the query (base64 data URL).
  const [image, setImage] = useState<{ dataUrl: string; name: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  // inline clip preview (opened from a result card)
  const [preview, setPreview] = useState<{ videoId: string; t: number } | null>(null);

  const onPickImage = (file: File) => {
    if (!file.type.startsWith("image/")) {
      toast.error(t("actions.upload"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setImage({ dataUrl: String(reader.result), name: file.name });
    reader.readAsDataURL(file);
  };

  const canRun = image != null || form.query.trim().length > 0;

  const run = async () => {
    if (!canRun) return;
    setRunning(true);
    try {
      const r = image
        ? await searchCorpusByImage({ image: image.dataUrl, top_n: form.top_n, group_by: form.group_by })
        : await searchCorpus({ query: form.query.trim(), top_n: form.top_n, group_by: form.group_by });
      setResult(r);
      if (r.shots.length === 0) toast.info(t("playground.search.no_matches_found"));
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t("actions.retry");
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const videoCount = result ? new Set(result.shots.map((s) => s.video_id)).size : 0;

  return (
    <PlaygroundShell
      title={t("playground.search.title")}
      subtitle={t("playground.search.subtitle")}
      formPanel={
        <FormPanel runLabel={t("actions.search")} onRun={run} running={running} canRun={canRun}>
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
                  placeholder={t("playground.search.placeholder")}
                  className="block min-h-[68px] w-full resize-none border-none bg-transparent text-[13px] leading-6 text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-gravel)]/80"
                />
                {image && (
                  <div className="mb-1 inline-flex items-center gap-2 rounded-[10px] border border-[var(--color-chalk)] bg-[var(--color-powder)] px-2 py-1">
                    <img src={image.dataUrl} alt={t("playground.search.entity_alt")} className="h-8 w-8 rounded object-cover" />
                    <span className="max-w-[140px] truncate text-[11px] text-[var(--color-gravel)]" title={image.name}>
                      {image.name}
                    </span>
                    <button
                      type="button"
                      aria-label={t("playground.search.remove_image")}
                      onClick={() => setImage(null)}
                      className="grid h-5 w-5 place-items-center rounded-full text-[var(--color-gravel)] hover:bg-[var(--color-chalk)] hover:text-[var(--color-obsidian)]"
                    >
                      <X size={12} />
                    </button>
                  </div>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) onPickImage(f);
                    e.target.value = "";
                  }}
                />
                <div className="flex items-center gap-x-2 pb-0.5 pt-1">
                  <button
                    type="button"
                    aria-label={t("playground.search.search_by_image")}
                    title={t("playground.search.search_by_image")}
                    onClick={() => fileRef.current?.click()}
                    className="grid h-7 w-7 place-items-center rounded-[8px] border border-[var(--color-chalk)] text-[var(--color-gravel)] transition-[border-radius,background-color] duration-200 ease-out hover:rounded-[12px] hover:bg-[var(--color-powder)]"
                  >
                    <ImageIcon size={14} />
                  </button>
                  <button
                    type="button"
                    aria-label={t("playground.search.search_by_entity")}
                    title={t("playground.search.search_by_entity")}
                    onClick={() => fileRef.current?.click()}
                    className="inline-flex h-7 items-center gap-1 rounded-[8px] border border-[var(--color-chalk)] px-2 text-[11px] text-[var(--color-gravel)] transition-[border-radius,background-color] duration-200 ease-out hover:rounded-[12px] hover:bg-[var(--color-powder)]"
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
                label={t("playground.search.opt_visual")}
                checked={searchOpts.visual}
                onChange={(v) => setSearchOpts((s) => ({ ...s, visual: v }))}
              />
              <CheckOption
                label={t("playground.search.opt_audio")}
                checked={searchOpts.audio}
                onChange={(v) => setSearchOpts((s) => ({ ...s, audio: v }))}
              />
              <CheckOption
                label={t("playground.search.opt_transcription")}
                checked={searchOpts.transcription}
                onChange={(v) => setSearchOpts((s) => ({ ...s, transcription: v }))}
              />
            </div>
          </Field>

          {searchOpts.transcription && (
            <Field label="transcription_options" type="ARRAY">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
                <CheckOption
                  label={t("playground.search.opt_lexical")}
                  checked={transcriptOpts.lexical}
                  onChange={(v) => setTranscriptOpts((s) => ({ ...s, lexical: v }))}
                />
                <CheckOption
                  label={t("playground.search.opt_semantic")}
                  checked={transcriptOpts.semantic}
                  onChange={(v) => setTranscriptOpts((s) => ({ ...s, semantic: v }))}
                />
              </div>
            </Field>
          )}

          <AdvancedSettings onReset={() => setForm({ ...form, top_n: 10, group_by: "video" })}>
            <Field label="group_by" type="ENUM" hint={t("playground.search.hint_group_by")}>
              <select
                value={form.group_by}
                onChange={(e) => setForm({ ...form, group_by: e.target.value as "clip" | "video" })}
                className="h-9 w-full rounded-lg border border-[var(--color-chalk)] bg-white px-3 text-[13px] focus:outline-none"
              >
                <option value="clip">clip</option>
                <option value="video">video</option>
              </select>
            </Field>
            <Field label="top_n" type="INTEGER" hint={t("playground.search.hint_top_n")}>
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
      browsePanel={
        // Right pane has three states, all in-place (TwelveLabs-style):
        //   1. a search has run    → result grid (with a "See video list" back link)
        //   2. an index is picked  → browse that index's videos
        //   3. nothing yet         → fall back to the examples panel (undefined)
        result ? (
          <div>
            <button
              type="button"
              onClick={() => setResult(null)}
              className="mb-3 inline-flex items-center gap-x-1 text-[13px] text-[var(--color-gravel)] transition hover:text-[var(--color-obsidian)] hover:underline"
            >
              <ChevronLeft size={16} />
              {t("playground.search.back_to_videos")}
            </button>
            <div className="mb-4 flex flex-wrap items-center gap-x-1.5">
              <p className="text-[15px] font-medium text-[var(--color-obsidian)]">
                {t("playground.search.results_title")}
              </p>
              <p className="text-[13px] text-[var(--color-gravel)]">
                {t(
                  result.shots.length === 1
                    ? "playground.search.results_counter_one"
                    : "playground.search.results_counter_other",
                  { count: result.shots.length, videos: videoCount },
                )}
              </p>
            </div>
            {result.shots.length === 0 ? (
              <p className="text-sm text-neutral-500">
                {t("playground.search.no_matches")}{" "}
                <Link className="underline" to="/playground/library">
                  {t("playground.search.no_matches_library")}
                </Link>
                .
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                {result.shots.map((s, i) => (
                  <ShotCard
                    key={`${s.video_id}-${s.idx}-${i}`}
                    rank={i + 1}
                    shot={s}
                    onPreview={() => setPreview({ videoId: s.video_id, t: s.t_start })}
                  />
                ))}
              </div>
            )}
            <VideoPreviewModal
              open={preview != null}
              videoId={preview?.videoId ?? null}
              startAt={preview?.t}
              onClose={() => setPreview(null)}
            />
          </div>
        ) : indexSelection ? (
          <IndexVideoBrowser indexId={indexSelection.id} />
        ) : undefined
      }
    />
  );
}

function ShotCard({ rank, shot, onPreview }: { rank: number; shot: CorpusShot; onPreview: () => void }) {
  const { t } = useTranslation();
  const [showTranscript, setShowTranscript] = useState(false);
  const range = `${formatSeconds(shot.t_start)} – ${formatSeconds(shot.t_end)}`;
  return (
    <div className="flex flex-col gap-y-3 rounded-3xl bg-[var(--color-powder)] p-5">
      {/* header: rank · filename · time range */}
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span className="grid h-6 min-w-6 place-items-center rounded-md border border-[var(--color-chalk)] px-1.5 font-mono text-[11px] text-[var(--color-obsidian)]">
          {rank}
        </span>
        <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--color-obsidian)]" title={shot.original_filename}>
          {shot.original_filename || "(untitled)"}
        </span>
        <span className="shrink-0 rounded-md border border-[var(--color-chalk)] px-1 font-mono text-[11px] text-[var(--color-obsidian)]">
          {range}
        </span>
      </div>

      {/* clip preview — click to play at the matched moment */}
      <button
        type="button"
        onClick={onPreview}
        aria-label={`Play ${shot.original_filename} at ${range}`}
        className="group relative block w-full overflow-hidden rounded-2xl bg-black focus-visible:outline-2 focus-visible:outline-signal"
      >
        <VideoThumb videoId={shot.video_id} shotIdx={shot.idx} className="aspect-video w-full" />
        <span className="absolute right-2 top-2 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-white">
          {(shot.score ?? shot.relevance ?? 0).toFixed(2)}
        </span>
      </button>

      {/* transcript (toggle) */}
      {showTranscript && shot.asr_text && (
        <p className="max-h-28 overflow-auto text-[12px] leading-snug text-[var(--color-gravel)]">
          "{shot.asr_text}"
        </p>
      )}

      {/* footer: transcript toggle · see full video */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          disabled={!shot.asr_text}
          aria-label={showTranscript ? t("actions.close") : t("playground.search.opt_transcription")}
          aria-pressed={showTranscript}
          onClick={() => setShowTranscript((v) => !v)}
          className="inline-flex h-7 items-center gap-1 rounded-lg border border-[var(--color-chalk)] px-1.5 text-[12px] text-[var(--color-obsidian)] hover:bg-white disabled:opacity-40"
        >
          <Captions size={15} />
        </button>
        <Link
          to={`/video/${shot.video_id}`}
          className="inline-flex items-center gap-1 text-[12px] text-[var(--color-obsidian)] hover:underline"
        >
          {t("playground.search.see_full_video")}
          <SquareArrowOutUpRight size={13} />
        </Link>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, History as HistoryIcon, Image as ImageIcon, Link as LinkIcon, Paperclip, RotateCcw, Save, Trash2, Video as VideoIcon, X } from "lucide-react";
import { toast } from "sonner";

import { VideoPlayer, type VideoPlayerHandle } from "@/components/video/VideoPlayer";
import {
  getStreamUrl,
  runSegment,
  type SegmentDefinition,
  type SegmentRunResponse,
  type TrackSegment,
  type VideoSummary,
} from "@/apis/videos.api";

import { VideoPickerModal, useVideoLibrary } from "./components/VideoPicker";
import { MultiTrackTimeline, type TimelineTrack } from "./components/MultiTrackTimeline";
import { MetadataPanel } from "./components/MetadataPanel";
import { PrettyDropdown, type DropdownItem } from "./components/PrettyDropdown";
import { SegmentBuilderModal } from "./components/SegmentDefinitionBuilder";
import {
  HistoryPanel,
  appendHistory,
  loadHistory,
  saveHistory,
  type SegmentRunHistoryEntry,
} from "./components/HistoryPanel";
import { PRESET_BY_ID, SEGMENT_PRESETS } from "./data/presets";
import {
  deleteSavedPreset,
  loadSavedPresets,
  upsertSavedPreset,
  type SavedPreset,
} from "./data/saved-presets";

type ViewMode = "Visual" | "JSON";

function defaultDefinitionsJson(): string {
  return JSON.stringify([SEGMENT_PRESETS[0].template], null, 2);
}

function tryParseDefinitions(text: string): { ok: true; defs: SegmentDefinition[] } | { ok: false; error: string } {
  try {
    const v = JSON.parse(text);
    if (!Array.isArray(v)) return { ok: false, error: "Top-level must be an array of definitions." };
    for (const d of v) {
      if (!d || typeof d !== "object") return { ok: false, error: "Each definition must be an object." };
      if (typeof d.id !== "string" || !d.id) return { ok: false, error: "Each definition needs a non-empty id." };
      if (typeof d.description !== "string") return { ok: false, error: "Each definition needs a description string." };
      if (!Array.isArray(d.fields)) return { ok: false, error: "Each definition needs a fields array." };
    }
    return { ok: true, defs: v as SegmentDefinition[] };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Invalid JSON." };
  }
}

const BUILTIN_ITEMS: DropdownItem[] = SEGMENT_PRESETS.map((p) => ({
  value: p.id,
  label: p.label,
  description: p.description,
  badge: p.needsRemote ? "GPU" : p.implemented ? undefined : "stub",
}));

function savedToDropdownItems(saved: SavedPreset[]): DropdownItem[] {
  return saved.map((p) => ({
    value: `__saved__${p.id}`,
    label: p.label,
    description: p.description || "Saved custom preset",
    badge: "saved",
  }));
}

export default function Segment() {
  const [video, setVideo] = useState<VideoSummary | null>(null);
  const [streamUrl, setStreamUrl] = useState<string>("");
  const [selectedPreset, setSelectedPreset] = useState<string>("shot_detection");
  const [definitionsJson, setDefinitionsJson] = useState<string>(defaultDefinitionsJson);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SegmentRunResponse | null>(null);
  const [view, setView] = useState<ViewMode>("Visual");
  const [playhead, setPlayhead] = useState<number>(0);
  const [showVideoSection, setShowVideoSection] = useState(true);
  const [showDefsSection, setShowDefsSection] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);

  const { videos, loading: videosLoading, error: videosError, refresh: refreshVideos } = useVideoLibrary();

  // History
  const [history, setHistory] = useState<SegmentRunHistoryEntry[]>(() => loadHistory());
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");

  // Advanced settings
  const [startS, setStartS] = useState<string>("");
  const [endS, setEndS] = useState<string>("");
  const [minDuration, setMinDuration] = useState<string>("");
  const [maxDuration, setMaxDuration] = useState<string>("");

  // Per-definition time-range filter (e.g. "0-10, 30-45") — Task 11.14.
  const [timeRangesText, setTimeRangesText] = useState<string>("");

  // Image attachment (base64 data URL) for the active definition — Task 11.13.
  const [imageAttachment, setImageAttachment] = useState<string | null>(null);

  // Saved-preset library — Task 11.15.
  const [savedPresets, setSavedPresets] = useState<SavedPreset[]>(() => loadSavedPresets());
  const [savePromptOpen, setSavePromptOpen] = useState(false);
  const [saveLabel, setSaveLabel] = useState("");

  // Segment Definition Builder modal.
  const [builderOpen, setBuilderOpen] = useState(false);

  const player = useRef<VideoPlayerHandle>(null);
  const formPlayer = useRef<VideoPlayerHandle>(null);

  useEffect(() => {
    if (!video) { setStreamUrl(""); return; }
    let alive = true;
    getStreamUrl(video.id)
      .then((u) => { if (alive) setStreamUrl(u); })
      .catch(() => setStreamUrl(""));
    return () => { alive = false; };
  }, [video?.id]);

  const parsed = useMemo(() => tryParseDefinitions(definitionsJson), [definitionsJson]);
  const canRun = !!video && !running && parsed.ok && parsed.defs.length > 0;

  const onPresetChange = (id: string) => {
    setSelectedPreset(id);
    if (id.startsWith("__saved__")) {
      const saved = savedPresets.find((p) => `__saved__${p.id}` === id);
      if (saved) {
        setDefinitionsJson(JSON.stringify([saved.definition], null, 2));
        setTimeRangesText((saved.definition.time_ranges || []).join(", "));
        setImageAttachment(saved.definition.image_attachment || null);
      }
      return;
    }
    const preset = PRESET_BY_ID[id];
    if (preset) {
      setDefinitionsJson(JSON.stringify([preset.template], null, 2));
      setTimeRangesText((preset.template.time_ranges || []).join(", "));
      setImageAttachment(preset.template.image_attachment || null);
    }
  };

  const presetItems: DropdownItem[] = useMemo(
    () => [...BUILTIN_ITEMS, ...savedToDropdownItems(savedPresets)],
    [savedPresets],
  );

  const onAttachImage = (file: File) => {
    if (file.size > 4 * 1024 * 1024) {
      toast.error("Image too large — keep it under 4MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setImageAttachment(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(file);
  };

  const onSaveCurrentAsPreset = () => {
    if (!parsed.ok || parsed.defs.length === 0) {
      toast.error("Fix the JSON before saving a preset.");
      return;
    }
    if (!saveLabel.trim()) {
      toast.error("Pick a label for the saved preset.");
      return;
    }
    const def = { ...parsed.defs[0] };
    const ranges = timeRangesText.trim();
    if (ranges) def.time_ranges = ranges.split(",").map((s) => s.trim()).filter(Boolean);
    if (imageAttachment) def.image_attachment = imageAttachment;
    const id = saveLabel.trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").slice(0, 40) || `custom_${Date.now()}`;
    const next = upsertSavedPreset({
      id, label: saveLabel.trim(), description: def.description || "", definition: { ...def, id },
    });
    setSavedPresets(next);
    setSelectedPreset(`__saved__${id}`);
    setSavePromptOpen(false);
    setSaveLabel("");
    toast.success(`Saved preset “${id}”`);
  };

  const onDeleteSelectedSaved = () => {
    if (!selectedPreset.startsWith("__saved__")) return;
    const id = selectedPreset.replace("__saved__", "");
    const next = deleteSavedPreset(id);
    setSavedPresets(next);
    setSelectedPreset("shot_detection");
    onPresetChange("shot_detection");
    toast.success(`Deleted preset “${id}”`);
  };

  const onCopyVideoUrl = async () => {
    if (!streamUrl) {
      toast.error("Pick a video first to copy its URL.");
      return;
    }
    try {
      await navigator.clipboard.writeText(streamUrl);
      toast.success("Video URL copied to clipboard.");
    } catch {
      toast.error("Clipboard blocked — copy manually from the player.");
    }
  };

  const onRun = async () => {
    if (!video || !parsed.ok) return;
    setRunning(true);
    try {
      const ranges = timeRangesText.split(",").map((s) => s.trim()).filter(Boolean);
      const defs = parsed.defs.map((d) => ({
        ...d,
        time_ranges: ranges.length > 0 ? ranges : d.time_ranges,
        image_attachment: imageAttachment ?? d.image_attachment,
      }));
      const res = await runSegment(video.id, {
        definitions: defs,
        start_s: startS ? parseFloat(startS) : undefined,
        end_s: endS ? parseFloat(endS) : undefined,
        min_duration_s: minDuration ? parseFloat(minDuration) : undefined,
        max_duration_s: maxDuration ? parseFloat(maxDuration) : undefined,
      });
      setResult(res);
      setView("Visual");
      const entry: SegmentRunHistoryEntry = {
        id: Date.now(),
        created_at: new Date().toISOString(),
        video_id: video.id,
        title: video.original_filename || parsed.defs[0]?.id || "segment_run",
        definitions: parsed.defs,
        result: res,
      };
      setHistory(appendHistory(entry));
      const empty = res.tracks.every((t) => t.segments.length === 0);
      if (empty) {
        toast.message("No segments produced — the selected definitions have no implemented segmenter yet.");
      }
    } catch (err) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Segment run failed";
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  };

  const onReset = () => {
    setStartS(""); setEndS(""); setMinDuration(""); setMaxDuration("");
  };

  const onPickHistory = (entry: SegmentRunHistoryEntry) => {
    const v = videos.find((vv) => vv.id === entry.video_id) ?? null;
    if (v) setVideo(v);
    setDefinitionsJson(JSON.stringify(entry.definitions, null, 2));
    if (entry.definitions[0]?.id && PRESET_BY_ID[entry.definitions[0].id]) {
      setSelectedPreset(entry.definitions[0].id);
    }
    setResult(entry.result);
    setView("Visual");
    setHistoryOpen(false);
  };

  const onClearHistory = () => {
    saveHistory([]);
    setHistory([]);
  };

  const duration = result?.duration_s ?? video?.duration_s ?? 0;

  const timelineTracks: TimelineTrack[] = useMemo(() => {
    if (!result) return [];
    return result.tracks.map((t) => {
      const preset = PRESET_BY_ID[t.definition_id];
      return {
        id: t.definition_id,
        label: t.definition_id,
        color: preset?.color ?? { fill: "#E5E5E5", stroke: "#404040" },
        blocks: t.segments.map((s) => ({ t_start: s.t_start, t_end: s.t_end })),
      };
    });
  }, [result]);

  const activeByTrack = useMemo(() => {
    const out: Record<string, TrackSegment | null> = {};
    if (!result) return out;
    for (const t of result.tracks) {
      out[t.definition_id] =
        t.segments.find((s) => playhead >= s.t_start && playhead < s.t_end) ?? null;
    }
    return out;
  }, [result, playhead]);

  const activeStartByTrack = useMemo(() => {
    const out: Record<string, number | null> = {};
    Object.entries(activeByTrack).forEach(([k, v]) => { out[k] = v ? v.t_start : null; });
    return out;
  }, [activeByTrack]);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[var(--color-eggshell)]">
      <header className="flex items-start justify-between px-8 pt-6 pb-4">
        <h1 className="text-[32px] font-light tracking-[-0.64px] text-[var(--color-obsidian)]">Segment</h1>
        <div className="flex items-center gap-2">
          <button className="inline-flex h-9 items-center gap-2 rounded-full border border-[var(--color-chalk)] bg-white px-4 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]">
            <span aria-hidden>📒</span> Learn <ChevronDown size={12} />
          </button>
          <button
            type="button"
            onClick={() => setHistoryOpen(true)}
            className="inline-flex h-9 items-center gap-2 rounded-full border border-[var(--color-chalk)] bg-white px-4 text-[13px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)]"
          >
            <HistoryIcon size={14} /> History
            {history.length > 0 && (
              <span className="ml-1 rounded-full bg-neutral-200 px-1.5 font-mono text-[10px] text-neutral-700">
                {history.length}
              </span>
            )}
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,380px)_minmax(0,1fr)] gap-6 px-8 pb-8">
        {/* LEFT — form */}
        <aside className="flex min-h-0 flex-col overflow-hidden rounded-[20px] bg-white shadow-[0_0_8px_0_rgba(28,29,27,0.12)]">
          <div className="flex-1 overflow-y-auto px-6 pt-5">
            {/* video */}
            <div className="flex flex-col gap-3 pb-3">
              <div className="flex h-6 w-full items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowVideoSection((v) => !v)}
                  className="flex items-center gap-x-1.5"
                >
                  {showVideoSection ? (
                    <ChevronDown size={12} className="text-neutral-500" />
                  ) : (
                    <ChevronRight size={12} className="text-neutral-500" />
                  )}
                  <span className="font-mono text-[11px] font-medium text-neutral-900 border-b border-dashed border-neutral-400">video</span>
                  <span className="font-mono text-[11px] font-medium text-red-500">*</span>
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPickerOpen(true)}
                    className="inline-flex items-center gap-1 rounded-[7px] border border-neutral-400 px-1.5 py-1 text-[10px] text-neutral-700 transition hover:rounded-[10px] hover:bg-neutral-200"
                  >
                    <VideoIcon size={12} /> Change Video
                  </button>
                  <button
                    type="button"
                    onClick={onCopyVideoUrl}
                    className="inline-flex items-center gap-1 rounded-[7px] border border-neutral-400 px-1.5 py-1 text-[10px] text-neutral-700 transition hover:rounded-[10px] hover:bg-neutral-200"
                  >
                    <LinkIcon size={12} /> Video URL
                  </button>
                </div>
              </div>

              {showVideoSection && (
                <div>
                  {video && streamUrl ? (
                    <div className="overflow-hidden rounded-[14px] bg-neutral-200">
                      <VideoPlayer
                        ref={formPlayer}
                        src={streamUrl}
                        onTimeUpdate={(t) => setPlayhead(t)}
                      />
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setPickerOpen(true)}
                      className="relative flex h-[180px] w-full items-center justify-center overflow-hidden rounded-[14px] border border-[var(--color-chalk)] bg-gradient-warm transition hover:shadow-hairline"
                    >
                      <span className="inline-flex items-center gap-2 rounded-md bg-[var(--color-obsidian)] px-3 py-1.5 text-[13px] text-white">
                        <VideoIcon size={13} />
                        {videosLoading ? "Loading…" : "Select a video"}
                      </span>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* segment_definitions */}
            <div className="flex flex-col gap-3 border-t border-neutral-200 pt-3 pb-3">
              <button
                type="button"
                onClick={() => setShowDefsSection((v) => !v)}
                className="flex h-6 items-center"
              >
                <div className="flex items-center gap-x-1.5">
                  {showDefsSection ? (
                    <ChevronDown size={12} className="text-neutral-500" />
                  ) : (
                    <ChevronRight size={12} className="text-neutral-500" />
                  )}
                  <span className="font-mono text-[11px] font-medium text-neutral-900 border-b border-dashed border-neutral-400">segment_definitions</span>
                  <span className="font-mono text-[11px] font-medium text-red-500">*</span>
                </div>
              </button>

              {showDefsSection && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <PrettyDropdown
                      items={presetItems}
                      value={selectedPreset}
                      onChange={onPresetChange}
                      className="flex-1"
                    />
                    <button
                      type="button"
                      onClick={() => setSavePromptOpen((v) => !v)}
                      className="inline-flex h-9 items-center gap-1 rounded-md border border-neutral-300 px-2 text-[12px] text-neutral-700 hover:bg-neutral-100"
                      title="Save current definition as a preset"
                    >
                      <Save size={12} /> Save
                    </button>
                    {selectedPreset.startsWith("__saved__") && (
                      <button
                        type="button"
                        onClick={onDeleteSelectedSaved}
                        className="grid h-9 w-9 place-items-center rounded-md border border-neutral-300 text-neutral-700 hover:bg-neutral-100"
                        title="Delete this saved preset"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>

                  {savePromptOpen && (
                    <div className="flex items-center gap-2 rounded-md border border-neutral-300 bg-neutral-50 p-2">
                      <input
                        autoFocus
                        value={saveLabel}
                        onChange={(e) => setSaveLabel(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && onSaveCurrentAsPreset()}
                        placeholder="Preset name (e.g. ‘NBA highlights v2’)"
                        className="flex-1 h-8 rounded border border-neutral-300 bg-white px-2 text-[12px] outline-none focus:border-neutral-700"
                      />
                      <button
                        type="button"
                        onClick={onSaveCurrentAsPreset}
                        className="rounded bg-neutral-800 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-neutral-700"
                      >
                        Save
                      </button>
                    </div>
                  )}

                  <div className="overflow-hidden rounded-lg bg-gradient-to-r from-[#F4A680] via-[#FFD3BE] to-[#FABA17] p-0.5">
                    <div className="relative rounded-[6px] bg-neutral-50">
                      <div className="absolute right-2 top-2 z-10 flex items-center gap-1">
                        <label
                          className="inline-flex cursor-pointer items-center gap-1 rounded-[7px] border border-neutral-700 bg-white px-1.5 py-1 text-[10px] text-neutral-900 shadow-[0_0_3px_0_rgba(29,28,27,0.4)] transition-colors hover:bg-neutral-100"
                          title="Attach a reference image (visual hint for the segmenter)"
                        >
                          <Paperclip size={12} />
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) onAttachImage(f);
                              e.target.value = "";
                            }}
                          />
                        </label>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-[7px] border border-neutral-700 bg-white px-1.5 py-1 text-[10px] text-neutral-900 shadow-[0_0_3px_0_rgba(29,28,27,0.4)] hover:bg-neutral-100"
                          title="Open the visual builder"
                          onClick={() => {
                            if (!parsed.ok) {
                              toast.error(`Fix JSON first: ${parsed.error}`);
                              return;
                            }
                            setBuilderOpen(true);
                          }}
                        >
                          {"</>"} Edit in Builder
                        </button>
                      </div>
                      <textarea
                        value={definitionsJson}
                        onChange={(e) => setDefinitionsJson(e.target.value)}
                        spellCheck={false}
                        className="block h-44 w-full resize-none rounded-[6px] bg-transparent px-3 py-2 pr-44 font-mono text-[12px] leading-5 text-neutral-900 focus:outline-none"
                      />
                    </div>
                  </div>
                  {imageAttachment && (
                    <div className="flex items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 p-2">
                      <img
                        src={imageAttachment}
                        alt="attached"
                        className="h-12 w-12 rounded object-cover"
                      />
                      <div className="flex-1 text-[11px] text-neutral-600">
                        <ImageIcon size={12} className="mr-1 inline" />
                        Image attached — will be sent with the segment definition.
                      </div>
                      <button
                        type="button"
                        onClick={() => setImageAttachment(null)}
                        className="grid h-6 w-6 place-items-center rounded text-neutral-500 hover:bg-neutral-200 hover:text-neutral-900"
                        aria-label="Remove attachment"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  )}

                  <div className="flex items-center justify-between gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1.5">
                    <span className="font-mono text-[11px] text-neutral-700">time_ranges</span>
                    <input
                      value={timeRangesText}
                      onChange={(e) => setTimeRangesText(e.target.value)}
                      placeholder="e.g. 0-10, 30-45"
                      className="h-7 w-[180px] rounded border border-neutral-300 bg-white px-2 text-[11px] outline-none focus:border-neutral-700"
                    />
                  </div>

                  {!parsed.ok && (
                    <p className="font-mono text-[11px] text-red-500">{parsed.error}</p>
                  )}
                </div>
              )}
            </div>

            {/* advanced settings */}
            <div className="flex items-center justify-between border-t border-neutral-200 pt-4 pb-2">
              <span className="text-[12px] font-semibold text-neutral-600">Advanced Settings</span>
              <button
                type="button"
                onClick={onReset}
                className="inline-flex items-center gap-1 rounded-[7px] px-1.5 py-1 text-[10px] text-neutral-900 hover:bg-neutral-100"
              >
                <RotateCcw size={12} /> Reset
              </button>
            </div>
            <div className="divide-y divide-neutral-200">
              <div className="flex items-center justify-between gap-2 py-3">
                <span className="font-mono text-[11px] font-medium text-neutral-900">start/end_time</span>
                <div className="flex items-center gap-1">
                  <input
                    inputMode="numeric"
                    placeholder="00:00"
                    value={startS}
                    onChange={(e) => setStartS(e.target.value)}
                    className="w-[72px] rounded border border-neutral-200 px-1 py-[5px] text-[13px] outline-none"
                  />
                  <span className="text-[13px] text-neutral-600">-</span>
                  <input
                    inputMode="numeric"
                    placeholder="00:00"
                    value={endS}
                    onChange={(e) => setEndS(e.target.value)}
                    className="w-[72px] rounded border border-neutral-200 px-1 py-[5px] text-[13px] outline-none"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 py-3">
                <span className="font-mono text-[11px] font-medium text-neutral-900">min_segment_duration</span>
                <input
                  inputMode="decimal"
                  placeholder="≥ 0"
                  value={minDuration}
                  onChange={(e) => setMinDuration(e.target.value)}
                  className="w-[112px] rounded border border-neutral-200 px-2 py-1 text-[13px] outline-none"
                />
              </div>
              <div className="flex items-center justify-between gap-3 py-3">
                <span className="font-mono text-[11px] font-medium text-neutral-900">max_segment_duration</span>
                <input
                  inputMode="decimal"
                  placeholder="≥ min duration"
                  value={maxDuration}
                  onChange={(e) => setMaxDuration(e.target.value)}
                  className="w-[112px] rounded border border-neutral-200 px-2 py-1 text-[13px] outline-none"
                />
              </div>
            </div>
          </div>

          {/* footer */}
          <div className="border-t border-neutral-200 px-6 py-4">
            <div className="mb-2 flex items-center justify-end gap-x-1 text-[13px] text-neutral-600">
              <span>with</span>
              <span className="font-semibold">tl-jockey pipeline</span>
            </div>
            <button
              type="button"
              disabled={!canRun}
              onClick={onRun}
              className="w-full rounded-[16px] bg-neutral-800 px-4 py-3 text-[15px] font-medium text-white transition hover:rounded-[20px] hover:bg-neutral-700 disabled:bg-neutral-300 disabled:text-neutral-500"
            >
              {running ? "Segmenting…" : "Segment"}
              <span className="ml-2 text-[12px] opacity-50">Ctrl+↵</span>
            </button>
          </div>
        </aside>

        {/* RIGHT — output */}
        <main className="flex min-h-0 flex-col">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex">
              <button
                type="button"
                onClick={() => setView("Visual")}
                className={`min-w-[80px] border border-neutral-800 px-3 py-1.5 text-[13px] rounded-l-md ${view === "Visual" ? "bg-neutral-800 text-white" : "bg-white text-neutral-900 hover:bg-neutral-100"}`}
              >
                Visual
              </button>
              <button
                type="button"
                onClick={() => setView("JSON")}
                className={`min-w-[80px] border border-neutral-800 px-3 py-1.5 text-[13px] rounded-r-md ${view === "JSON" ? "bg-neutral-800 text-white" : "bg-white text-neutral-900 hover:bg-neutral-100"}`}
              >
                JSON
              </button>
            </div>
            <div className="flex items-center gap-2">
              {result && (
                <span className="rounded-lg border border-green-700 bg-green-900 px-2 py-0 font-mono text-[14px] font-medium leading-5 text-green-100">
                  200 OK
                </span>
              )}
            </div>
          </div>

          {!result && (
            <div className="flex flex-1 items-center justify-center rounded-[20px] border border-dashed border-neutral-300 bg-white text-sm text-neutral-500">
              Pick a video and hit Segment to see the multi-track timeline + metadata.
            </div>
          )}

          {result && view === "Visual" && (
            <div className="flex min-h-0 flex-1 gap-6">
              <div className="flex min-w-0 flex-1 flex-col gap-3 overflow-y-auto">
                {streamUrl && (
                  <div className="overflow-hidden rounded-[20px] bg-neutral-200">
                    <VideoPlayer
                      ref={player}
                      src={streamUrl}
                      onTimeUpdate={(t) => setPlayhead(t)}
                    />
                  </div>
                )}
                <MultiTrackTimeline
                  duration={duration}
                  tracks={timelineTracks}
                  playhead={playhead}
                  onSeek={(t) => {
                    player.current?.seekTo(t);
                    formPlayer.current?.seekTo(t);
                    setPlayhead(t);
                  }}
                  activePerTrack={activeStartByTrack}
                />
                <div className="flex items-center justify-between rounded-[12px] bg-neutral-300 px-5 py-2 text-[13px]">
                  <span className="text-neutral-700">tl-jockey pipeline · generated just now</span>
                  <span className="text-neutral-700">
                    {result.tracks.reduce((s, t) => s + t.segments.length, 0)} segments
                  </span>
                </div>
              </div>

              <div className="w-[320px] shrink-0 overflow-y-auto">
                <MetadataPanel
                  tracks={result.tracks}
                  presetById={PRESET_BY_ID}
                  activeByTrack={activeByTrack}
                  onSeek={(t) => {
                    player.current?.seekTo(t);
                    formPlayer.current?.seekTo(t);
                    setPlayhead(t);
                  }}
                />
              </div>
            </div>
          )}

          {result && view === "JSON" && (
            <pre className="flex-1 overflow-auto rounded-[20px] bg-neutral-900 p-4 font-mono text-[12px] text-neutral-100">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </main>
      </div>

      <VideoPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        videos={videos}
        loading={videosLoading}
        error={videosError}
        selectedId={video?.id}
        onSelect={(v) => {
          setVideo(v);
          setPickerOpen(false);
        }}
        onRefresh={refreshVideos}
      />

      <HistoryPanel
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        entries={history}
        filter={historyFilter}
        onFilterChange={setHistoryFilter}
        onPick={onPickHistory}
        onClear={onClearHistory}
      />

      <SegmentBuilderModal
        open={builderOpen}
        value={parsed.ok ? parsed.defs : []}
        onChange={(next) => setDefinitionsJson(JSON.stringify(next, null, 2))}
        onClose={() => setBuilderOpen(false)}
      />
    </div>
  );
}

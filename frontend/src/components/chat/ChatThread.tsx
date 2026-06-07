import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User } from "lucide-react";

import type { VideoSummary } from "@/apis/videos.api";
import { streamChat, type ChatEvent } from "@/apis/chat.api";
import type { ChatScopeValue } from "@/pages/chat/components/ChatScopeBar";
import { AgentsThinking, type ThinkingStep } from "./AgentsThinking";
import { ChatComposer } from "./ChatComposer";
import { BrandAvatar } from "@/components/brand/BrandAvatar";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import { VideoSearchResults, type ClipResult } from "./VideoSearchResults";
import { VideoSummaryCard } from "./VideoSummaryCard";

interface AttachmentSnapshot { id: string; name: string; }

interface Turn {
  user: string;
  attachments: AttachmentSnapshot[];
  image?: string;
  assistant: string;
  steps: ThinkingStep[];
  resultClips: ClipResult[];
  summaries: { videoId: string; text: string }[];
}

interface Props {
  initialAttached?: VideoSummary[];
  scope?: ChatScopeValue;
}

export function ChatThread({ initialAttached = [], scope }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [attached, setAttached] = useState<VideoSummary[]>(initialAttached);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ videoId: string; t?: number } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  const send = async (message: string, videoIds: string[], image?: string) => {
    setBusy(true);
    const snapshots: AttachmentSnapshot[] = attached.map((v) => ({ id: v.id, name: v.original_filename }));
    const newTurn: Turn = {
      user: message,
      attachments: snapshots,
      image,
      assistant: "",
      steps: [],
      resultClips: [],
      summaries: [],
    };
    setTurns((t) => [...t, newTurn]);

    const updateLast = (patch: (t: Turn) => Turn) =>
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? patch(x) : x)));

    const onEvent = (ev: ChatEvent) => {
      switch (ev.type) {
        case "thought":
          updateLast((t) => {
            const last = t.steps[t.steps.length - 1];
            if (last && last.type === "thought" && last.agent === ev.agent) {
              const merged = { ...last, text: (last.text ?? "") + ev.delta };
              return { ...t, steps: [...t.steps.slice(0, -1), merged] };
            }
            return { ...t, steps: [...t.steps, { type: "thought", agent: ev.agent, text: ev.delta }] };
          });
          break;
        case "tool_call":
          updateLast((t) => ({ ...t, steps: [...t.steps, { type: "tool_call", tool: ev.tool, args: ev.args }] }));
          break;
        case "tool_result":
          updateLast((t) => {
            const next: Turn = { ...t, steps: [...t.steps, { type: "tool_result", tool: ev.tool, result: ev.result }] };
            const clips = extractClips(ev.tool, ev.result);
            if (clips.length) next.resultClips = [...next.resultClips, ...clips];
            const summary = extractSummary(ev.tool, ev.result, videoIds);
            if (summary) next.summaries = [...next.summaries, summary];
            return next;
          });
          break;
        case "message":
          updateLast((t) => ({ ...t, assistant: t.assistant + ev.delta }));
          break;
        case "end":
          break;
      }
    };

    // Resolve final scope: when the user has explicitly chosen an Index (subset
    // or whole), the scope bar wins over drag-attached videos. In subset mode we
    // forward the picked video_ids; in whole-index mode we send the empty list
    // so the backend expands to every video in the index.
    let finalVideoIds: string[] | undefined = videoIds.length ? videoIds : undefined;
    let finalIndexId: string | undefined;
    if (scope) {
      if (scope.mode === "whole" && scope.indexId) {
        finalIndexId = scope.indexId;
        finalVideoIds = undefined;
      } else if (scope.mode === "subset" && scope.indexId) {
        finalIndexId = scope.indexId;
        finalVideoIds = scope.videoIds.length ? scope.videoIds : undefined;
      }
    }

    try {
      await streamChat({
        message,
        video_ids: finalVideoIds,
        index_id: finalIndexId,
        image,
        onEvent,
      });
    } finally {
      setBusy(false);
    }
  };

  const addAttachment = (video: VideoSummary) => {
    setAttached((cur) => (cur.find((v) => v.id === video.id) ? cur : [...cur, video]));
  };
  const removeAttachment = (id: string) => setAttached((cur) => cur.filter((v) => v.id !== id));

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-8 overflow-auto px-1 py-4">
        {turns.length === 0 && (
          <div className="grid h-full place-items-center text-sm text-neutral-400">
            Ask Jockey anything about your videos.
          </div>
        )}

        {turns.map((t, i) => {
          const isLastTurn = i === turns.length - 1;
          const turnComplete = !isLastTurn || !busy;
          return (
          <div key={i} className="space-y-3">
            <div className="text-sm">
              <div className="mb-1 inline-flex items-center gap-2 text-xs font-medium text-neutral-500">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-neutral-200 text-neutral-600">
                  <User size={12} />
                </span>
                You
              </div>
              {t.image && (
                <img
                  src={t.image}
                  alt="attached"
                  className="mb-2 h-28 w-28 rounded-xl border border-neutral-200 object-cover"
                />
              )}
              <p className="text-neutral-900">{t.user}</p>
              {t.attachments.length > 0 && (
                <p className="mt-1 text-xs text-neutral-500">
                  Attached: {t.attachments.map((a) => a.name).join(", ")}
                </p>
              )}
            </div>

            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 text-xs font-medium text-neutral-700">
                <BrandAvatar size={20} />
                Jockey
              </div>

              {t.steps.length > 0 && (
                <AgentsThinking
                  steps={t.steps}
                  assistantHasContent={t.assistant.length > 0}
                  complete={turnComplete}
                />
              )}

              {/* Final output (clips / summary cards) only after the agent
                  finishes thinking — otherwise tool_result events render the
                  answer mid-stream, before the later thinking steps appear. */}
              {turnComplete && t.resultClips.length > 0 && (
                <VideoSearchResults
                  clips={t.resultClips}
                  onPreview={(videoId, time) => setPreview({ videoId, t: time })}
                />
              )}

              {turnComplete && t.summaries.length > 0 && (
                <div className="divide-y divide-neutral-100">
                  {t.summaries.map((s, j) => (
                    <VideoSummaryCard
                      key={j}
                      videoId={s.videoId}
                      text={s.text}
                      onPreview={() => setPreview({ videoId: s.videoId })}
                    />
                  ))}
                </div>
              )}

              {t.assistant && t.resultClips.length === 0 && t.summaries.length === 0 && (
                <div className="text-sm leading-relaxed text-neutral-900 [&_p]:my-2 [&_code]:rounded [&_code]:bg-neutral-100 [&_code]:px-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-neutral-100 [&_pre]:p-3 [&_pre]:text-xs">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.assistant}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        );
        })}
        <div ref={bottom} />
      </div>

      <div className="border-t border-neutral-100 pt-3">
        <ChatComposer
          attached={attached}
          onRemove={removeAttachment}
          onDropVideo={addAttachment}
          onSend={send}
          busy={busy}
        />
      </div>

      <VideoPreviewModal
        open={!!preview}
        videoId={preview?.videoId ?? null}
        startAt={preview?.t}
        onClose={() => setPreview(null)}
      />
    </div>
  );
}

function extractClips(tool: string, result: unknown): ClipResult[] {
  if (!result || typeof result !== "object") return [];
  const r = result as Record<string, unknown>;
  const videoId = (r.video_id as string) ?? "";
  if (!(tool.includes("ground") || tool.includes("search"))) return [];

  // ground_video returns time-range `moments` (no shots). Surface the TOP-3 as
  // clickable clip cards — the top-1 isn't always the right moment, so the user
  // can scan candidates. Each plays from its t_start; score shown as a %.
  if (tool.includes("ground")) {
    const moments = (r.moments as Array<Record<string, unknown>>) ?? [];
    return moments
      .filter((m) => typeof m.t_start === "number" && typeof m.t_end === "number")
      .sort((a, b) => (typeof b.score === "number" ? b.score : 0) - (typeof a.score === "number" ? a.score : 0))
      .slice(0, 3)
      .map((m) => ({
        video_id: videoId,
        t_start: m.t_start as number,
        t_end: m.t_end as number,
        score: typeof m.score === "number" ? (m.score as number) : undefined,
        display_mode: "clip" as const,
      }));
  }

  const shots = (r.shots as Array<Record<string, unknown>>) ?? [];
  // group_by is the LLM-chosen presentation hint coming from the corpus search.
  // "video" → one result per distinct video; "clip" → keep all matched clips.
  const groupBy = r.group_by === "video" ? "video" : "clip";

  const clips: ClipResult[] = shots
    .filter((s) => typeof s.t_start === "number" && typeof s.t_end === "number")
    .map((s) => ({
      video_id: (s.video_id as string) ?? videoId,
      shot_idx: typeof s.idx === "number" ? (s.idx as number) : undefined,
      t_start: s.t_start as number,
      t_end: s.t_end as number,
      video_duration_s: typeof s.video_duration_s === "number" ? (s.video_duration_s as number) : undefined,
      original_filename: typeof s.original_filename === "string" ? (s.original_filename as string) : undefined,
      display_mode: groupBy === "video" ? "parent_video" : "clip",
    }));

  // Frontend fallback: if every clip points at the same video_id, the LLM probably
  // should have grouped by video. Collapse to one parent-video tile so we don't
  // render N near-identical clips of the same source.
  if (clips.length > 1) {
    const distinct = new Set(clips.map((c) => c.video_id));
    if (distinct.size === 1) {
      const top = clips[0];
      return [{ ...top, display_mode: "parent_video" }];
    }
  }

  // For parent_video mode, dedupe by video_id (keep the highest-scoring shot per video).
  if (groupBy === "video") {
    const seen = new Set<string>();
    return clips.filter((c) => (seen.has(c.video_id) ? false : (seen.add(c.video_id), true)));
  }

  return clips;
}

function extractSummary(tool: string, result: unknown, fallbackIds: string[]): { videoId: string; text: string } | null {
  if (!result || typeof result !== "object") return null;
  if (!(tool.includes("qa") || tool.includes("ask") || tool.includes("text-generation"))) return null;
  const r = result as Record<string, unknown>;
  const text = (r.answer as string) ?? (r.text as string) ?? "";
  if (!text) return null;
  const videoId = (r.video_id as string) ?? fallbackIds[0] ?? "";
  return { videoId, text };
}

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { VideoSummary } from "@/apis/videos.api";
import { streamChat, type ChatEvent } from "@/apis/chat.api";
import { AgentsThinking, type ThinkingStep } from "./AgentsThinking";
import { ChatComposer } from "./ChatComposer";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import { VideoSearchResults, type ClipResult } from "./VideoSearchResults";
import { VideoSummaryCard } from "./VideoSummaryCard";

interface AttachmentSnapshot { id: string; name: string; }

interface Turn {
  user: string;
  attachments: AttachmentSnapshot[];
  assistant: string;
  steps: ThinkingStep[];
  resultClips: ClipResult[];
  summaries: { videoId: string; text: string }[];
}

interface Props {
  initialAttached?: VideoSummary[];
}

export function ChatThread({ initialAttached = [] }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [attached, setAttached] = useState<VideoSummary[]>(initialAttached);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ videoId: string; t?: number } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  const send = async (message: string, videoIds: string[]) => {
    setBusy(true);
    const snapshots: AttachmentSnapshot[] = attached.map((v) => ({ id: v.id, name: v.original_filename }));
    const newTurn: Turn = {
      user: message,
      attachments: snapshots,
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

    try {
      await streamChat({ message, video_ids: videoIds.length ? videoIds : undefined, onEvent });
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

        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            <div className="text-sm">
              <div className="mb-1 inline-flex items-center gap-2 text-xs font-medium text-neutral-500">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-neutral-200 text-[10px]">You</span>
              </div>
              <p className="text-neutral-900">{t.user}</p>
              {t.attachments.length > 0 && (
                <p className="mt-1 text-xs text-neutral-500">
                  Attached: {t.attachments.map((a) => a.name).join(", ")}
                </p>
              )}
            </div>

            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 text-xs font-medium text-neutral-700">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-neutral-900 text-[9px] font-bold text-white">J</span>
                Jockey
              </div>

              {t.steps.length > 0 && <AgentsThinking steps={t.steps} />}

              {t.resultClips.length > 0 && (
                <VideoSearchResults
                  clips={t.resultClips}
                  onPreview={(videoId, time) => setPreview({ videoId, t: time })}
                />
              )}

              {t.summaries.length > 0 && (
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

              {t.assistant && (
                <div className="text-sm leading-relaxed text-neutral-900 [&_p]:my-2 [&_code]:rounded [&_code]:bg-neutral-100 [&_code]:px-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-neutral-100 [&_pre]:p-3 [&_pre]:text-xs">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.assistant}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}
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
  if (tool.includes("ground") || tool.includes("search")) {
    const shots = (r.shots as Array<Record<string, unknown>>) ?? [];
    return shots
      .filter((s) => typeof s.t_start === "number" && typeof s.t_end === "number")
      .map((s) => ({
        video_id: (s.video_id as string) ?? videoId,
        shot_idx: typeof s.idx === "number" ? (s.idx as number) : undefined,
        t_start: s.t_start as number,
        t_end: s.t_end as number,
      }));
  }
  return [];
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

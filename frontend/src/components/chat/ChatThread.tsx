import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Play, User } from "lucide-react";

import { getVideo, type VideoSummary } from "@/apis/videos.api";
import { getConversation, streamChat, type ChatEvent, type PersistedMessage } from "@/apis/chat.api";
import { qk } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import type { ChatScopeValue } from "@/pages/chat/components/ChatScopeBar";
import { AgentsThinking, type ThinkingStep } from "./AgentsThinking";
import { ChatComposer } from "./ChatComposer";
import { BrandAvatar } from "@/components/brand/BrandAvatar";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import { VideoThumb } from "@/components/video/VideoThumb";
import { ImageLightbox } from "./ImageLightbox";
import { VideoSearchResults, type ClipResult } from "./VideoSearchResults";
import { EditedClipCard, type EditResult } from "./EditedClipCard";
import { VideoSummaryCard } from "./VideoSummaryCard";
import { linkifyTimestamps, seekMarkdownComponents } from "./timestampLink";

interface AttachmentSnapshot { id: string; name: string; }

interface Turn {
  user: string;
  attachments: AttachmentSnapshot[];
  image?: string;
  assistant: string;
  steps: ThinkingStep[];
  resultClips: ClipResult[];
  summaries: { videoId: string; text: string }[];
  edits: EditResult[];
}

interface Props {
  initialAttached?: VideoSummary[];
  scope?: ChatScopeValue;
  /** When set (from /chat/:conversationId), load + resume this conversation. */
  conversationId?: string;
}

export function ChatThread({ initialAttached = [], scope, conversationId }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [attached, setAttached] = useState<VideoSummary[]>(initialAttached);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ videoId: string; t?: number } | null>(null);
  const [imgPreview, setImgPreview] = useState<string | null>(null);
  // The conversation this thread is bound to. A ref (not state): streamChat
  // reads it per send, and updating it must not re-render mid-stream.
  const convIdRef = useRef<string | undefined>(undefined);
  const [historyState, setHistoryState] = useState<"idle" | "loading" | "error">("idle");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Pin to the latest turn by scrolling the message CONTAINER — not
  // scrollIntoView, which scrolls the nearest scrollable ancestor (the page),
  // yanking the whole layout down on a new conversation.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns]);

  // Load persisted history when the URL points at a conversation we don't
  // already hold (thread switch / deep link). The navigate-after-first-reply
  // case is a no-op because convIdRef already matches. conversationId →
  // undefined means "New chat": reset to a fresh thread.
  useEffect(() => {
    if (!conversationId) {
      if (convIdRef.current) {
        convIdRef.current = undefined;
        setTurns([]);
        setAttached([]);
        setHistoryState("idle");
      }
      return;
    }
    if (conversationId === convIdRef.current) return;
    convIdRef.current = conversationId;
    let cancelled = false;
    setHistoryState("loading");
    setTurns([]);
    setAttached([]);
    (async () => {
      try {
        const convo = await getConversation(conversationId);
        if (cancelled) return;
        // Resolve the conversation's attached video FIRST so its filename is
        // available to re-render the per-turn attachment thumbnail. Single-video
        // scope keeps one video attached across every turn, so each user turn
        // re-shows it on reload — matching the live session (where `attached`
        // persists and every sent turn carries it).
        let attachedVideo: VideoSummary | undefined;
        if (convo.video_id) {
          try {
            attachedVideo = await getVideo(convo.video_id);
          } catch {
            /* the video may have been deleted since — resume without it */
          }
        }
        // Resolve filenames for every video a turn acted on (a turn may have used
        // a video other than the conversation's pinned one), so each per-turn
        // attachment chip shows the correct name on reload.
        const videoNames: Record<string, string> = {};
        if (convo.video_id && attachedVideo) videoNames[convo.video_id] = attachedVideo.original_filename;
        const refIds = new Set<string>();
        for (const m of convo.messages) {
          const v = turnActedVideoId(m.tool_calls);
          if (v && !(v in videoNames)) refIds.add(v);
        }
        await Promise.all(
          [...refIds].map(async (id) => {
            try { videoNames[id] = (await getVideo(id)).original_filename; } catch { /* deleted */ }
          }),
        );
        if (cancelled) return;
        setTurns(turnsFromMessages(convo.messages, convo.video_id ?? undefined, attachedVideo?.original_filename, videoNames));
        setHistoryState("idle");
        if (attachedVideo) setAttached([attachedVideo]);
      } catch {
        if (!cancelled) setHistoryState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

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
      edits: [],
    };
    setTurns((prev) => [...prev, newTurn]);

    const updateLast = (patch: (turn: Turn) => Turn) =>
      setTurns((prev) => prev.map((x, i) => (i === prev.length - 1 ? patch(x) : x)));

    const onEvent = (ev: ChatEvent) => {
      switch (ev.type) {
        case "thought":
          updateLast((turn) => {
            const last = turn.steps[turn.steps.length - 1];
            if (last && last.type === "thought" && last.agent === ev.agent) {
              const merged = { ...last, text: (last.text ?? "") + ev.delta };
              return { ...turn, steps: [...turn.steps.slice(0, -1), merged] };
            }
            return { ...turn, steps: [...turn.steps, { type: "thought", agent: ev.agent, text: ev.delta }] };
          });
          break;
        case "tool_call":
          updateLast((turn) => ({ ...turn, steps: [...turn.steps, { type: "tool_call", tool: ev.tool, args: ev.args }] }));
          break;
        case "tool_result":
          updateLast((turn) => {
            const next: Turn = { ...turn, steps: [...turn.steps, { type: "tool_result", tool: ev.tool, result: ev.result }] };
            const clips = extractClips(ev.tool, ev.result);
            if (clips.length) next.resultClips = [...next.resultClips, ...clips];
            const summary = extractSummary(ev.tool, ev.result, videoIds);
            if (summary) next.summaries = [...next.summaries, summary];
            const edit = extractEdit(ev.tool, ev.result);
            if (edit) next.edits = [...next.edits, edit];
            return next;
          });
          break;
        case "message":
          updateLast((turn) => ({ ...turn, assistant: turn.assistant + ev.delta }));
          break;
        case "end":
          if (!convIdRef.current && ev.conversation_id) {
            // First reply of a brand-new thread: bind it and reflect in the URL
            // so refresh/share resumes it. replace (not push) — "back" should
            // not step through /workspace → /chat/:id.
            convIdRef.current = ev.conversation_id;
            navigate(`/chat/${ev.conversation_id}`, { replace: true });
          }
          void queryClient.invalidateQueries({ queryKey: qk.conversations(user?.id) });
          break;
      }
    };

    // Resolve final scope: in "Selected index" (whole) mode the chosen Index wins
    // over drag-attached videos — send the index_id + empty video list so the
    // backend expands to every video in the index (KG). Otherwise ("General") the
    // drag-attached videos drive scope.
    let finalVideoIds: string[] | undefined = videoIds.length ? videoIds : undefined;
    let finalIndexId: string | undefined;
    if (scope && scope.mode === "whole" && scope.indexId) {
      finalIndexId = scope.indexId;
      finalVideoIds = undefined;
    }

    try {
      await streamChat({
        conversation_id: convIdRef.current,
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

  const MAX_ATTACHED = 5;
  const addAttachment = (video: VideoSummary) => {
    // Accumulate dragged videos (drag several in, one per drop) up to MAX_ATTACHED,
    // deduped by id — all scopes. The backend treats the MOST RECENTLY attached as
    // the "this video" subject (see chat.py / router.md), so building up a set is
    // safe; the user removes any they didn't mean. Excess past the cap is ignored.
    setAttached((cur) => {
      if (cur.find((v) => v.id === video.id)) return cur;
      if (cur.length >= MAX_ATTACHED) return cur;
      return [...cur, video];
    });
  };
  const removeAttachment = (id: string) => setAttached((cur) => cur.filter((v) => v.id !== id));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="flex-1 space-y-8 overflow-auto px-1 py-4">
        {historyState === "loading" && (
          <div className="grid h-full place-items-center text-sm text-neutral-400">
            {t("chat.thread.history_loading")}
          </div>
        )}
        {historyState === "error" && (
          <div className="grid h-full place-items-center text-sm text-neutral-400">
            {t("chat.thread.history_load_failed")}
          </div>
        )}
        {historyState === "idle" && turns.length === 0 && (
          <div className="grid h-full place-items-center text-sm text-neutral-400">
            {t("chat.thread.empty_state")}
          </div>
        )}

        {turns.map((turn, i) => {
          const isLastTurn = i === turns.length - 1;
          const turnComplete = !isLastTurn || !busy;
          // Video that this turn's inline [mm:ss] citations should seek.
          const turnVideoId = turn.attachments[0]?.id ?? attached[0]?.id;
          return (
          <div key={i} className="space-y-3">
            <div className="text-sm">
              <div className="mb-1 inline-flex items-center gap-2 text-xs font-medium text-neutral-500">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-neutral-200 text-neutral-600">
                  <User size={12} />
                </span>
                {t("chat.thread.you")}
              </div>
              {turn.image && (
                <button
                  type="button"
                  onClick={() => setImgPreview(turn.image!)}
                  aria-label={t("chat.thread.open_image_aria")}
                  className="mb-2 block overflow-hidden rounded-xl border border-neutral-200 transition hover:border-neutral-400 hover:opacity-95 focus-visible:outline-2 focus-visible:outline-signal"
                >
                  <img
                    src={turn.image}
                    alt={t("chat.thread.attached_image_alt")}
                    className="h-28 w-28 object-cover"
                  />
                </button>
              )}
              <p className="text-neutral-900">{turn.user}</p>
              {turn.attachments.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2.5">
                  {turn.attachments.map((a) => (
                    <figure key={a.id} className="w-44">
                      <div
                        role="button"
                        tabIndex={0}
                        title={a.name}
                        aria-label={t("chat.thread.play_video_aria", { name: a.name })}
                        onClick={() => setPreview({ videoId: a.id })}
                        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPreview({ videoId: a.id }); } }}
                        className="group relative cursor-pointer overflow-hidden rounded-lg focus-visible:outline-2 focus-visible:outline-signal"
                      >
                        <VideoThumb videoId={a.id} className="aspect-video w-44" />
                        <span className="pointer-events-none absolute inset-0 grid place-items-center bg-black/0 transition group-hover:bg-black/15">
                          <span className="grid h-9 w-9 place-items-center rounded-full bg-black/55 text-white shadow">
                            <Play size={16} className="ml-0.5" />
                          </span>
                        </span>
                      </div>
                      {a.name && (
                        <figcaption className="mt-1 truncate text-xs text-neutral-500" title={a.name}>
                          {a.name}
                        </figcaption>
                      )}
                    </figure>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 text-xs font-medium text-neutral-700">
                <BrandAvatar size={20} />
                {t("chat.thread.title")}
              </div>

              {turn.steps.length > 0 && (
                <AgentsThinking
                  steps={turn.steps}
                  assistantHasContent={turn.assistant.length > 0}
                  complete={turnComplete}
                />
              )}

              {/* Final output (clips / summary cards) only after the agent
                  finishes thinking — otherwise tool_result events render the
                  answer mid-stream, before the later thinking steps appear. */}
              {turnComplete && turn.resultClips.length > 0 && (
                <VideoSearchResults
                  clips={turn.resultClips}
                  onPreview={(videoId, time) => setPreview({ videoId, t: time })}
                />
              )}

              {turnComplete && turn.summaries.length > 0 && (
                <div className="divide-y divide-neutral-100">
                  {turn.summaries.map((s, j) => (
                    <VideoSummaryCard
                      key={j}
                      videoId={s.videoId}
                      text={s.text}
                      onPreview={() => setPreview({ videoId: s.videoId })}
                      onSeek={(sec) => setPreview({ videoId: s.videoId, t: sec })}
                    />
                  ))}
                </div>
              )}

              {turnComplete && turn.edits.length > 0 && (
                <div className="space-y-2">
                  {turn.edits.map((e) => (
                    <EditedClipCard key={e.edit_id} edit={e} />
                  ))}
                </div>
              )}

              {turn.assistant && turn.resultClips.length === 0 && turn.summaries.length === 0 && (
                <div className="text-sm leading-relaxed text-neutral-900 [&_p]:my-2 [&_code]:rounded [&_code]:bg-neutral-100 [&_code]:px-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-neutral-100 [&_pre]:p-3 [&_pre]:text-xs">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={seekMarkdownComponents(
                      (sec) => turnVideoId && setPreview({ videoId: turnVideoId, t: sec }),
                    )}
                  >
                    {linkifyTimestamps(turn.assistant)}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        );
        })}
      </div>

      <div className="shrink-0 border-t border-neutral-100 pt-3">
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

      <ImageLightbox src={imgPreview} onClose={() => setImgPreview(null)} />
    </div>
  );
}

function extractClips(tool: string, result: unknown): ClipResult[] {
  if (!result || typeof result !== "object") return [];
  const r = result as Record<string, unknown>;
  const videoId = (r.video_id as string) ?? "";
  if (!(tool.includes("ground") || tool.includes("search") || tool.includes("highlight") || tool.includes("similar") || tool.includes("sound") || tool.includes("scene")))
    return [];

  // find_sounds returns shots (one video) with audio_tags + asr_text but no
  // caption/video_id per shot. Surface each as a moment card; caption = the ASR
  // snippet or the matched audio tags. Never collapse to a parent tile — these
  // are distinct moments WITHIN one video.
  if (tool.includes("sound")) {
    const shots = (r.shots as Array<Record<string, unknown>>) ?? [];
    return shots
      .filter((s) => typeof s.t_start === "number" && typeof s.t_end === "number")
      .map((s) => {
        const tags = Array.isArray(s.audio_tags)
          ? (s.audio_tags as Array<Record<string, unknown>>)
              .map((t) => (typeof t.label === "string" ? t.label : null))
              .filter(Boolean)
              .slice(0, 4)
              .join(", ")
          : "";
        return {
          video_id: videoId,
          shot_idx: typeof s.idx === "number" ? (s.idx as number) : undefined,
          t_start: s.t_start as number,
          t_end: s.t_end as number,
          // The label is the DETECTED SOUND (audio tags), not the ASR transcript —
          // a "basketball bounce" search shouldn't show unrelated commentary speech.
          caption: tags ? `🔊 ${tags}` : undefined,
          display_mode: "clip" as const,
        };
      });
  }

  // find_similar returns whole-video `results` — render each as a parent-video
  // tile (plays from t=0, shows full duration), top-5, ranked by score.
  if (tool.includes("similar")) {
    const results = (r.results as Array<Record<string, unknown>>) ?? [];
    return results
      .filter((v) => typeof v.video_id === "string")
      .slice(0, 5)
      .map((v) => ({
        video_id: v.video_id as string,
        t_start: 0,
        t_end: typeof v.duration_s === "number" ? (v.duration_s as number) : 0,
        video_duration_s: typeof v.duration_s === "number" ? (v.duration_s as number) : undefined,
        original_filename: typeof v.original_filename === "string" ? (v.original_filename as string) : undefined,
        score: typeof v.score === "number" ? (v.score as number) : undefined,
        display_mode: "parent_video" as const,
      }));
  }

  // ground_video + get_highlights both return time-range `moments`. Surface the
  // TOP-3 as clickable clip cards — the top-1 isn't always the right moment, so
  // the user can scan candidates. Each plays from its t_start.
  // Grounding `score` is a 0..1 relevance the user can compare, so show it as %.
  // Highlight `score` is a QD-DETR saliency value (can be negative, not a match
  // %) — surface only the MOMENT for highlights, no misleading percentage.
  if (tool.includes("ground") || tool.includes("highlight")) {
    const isHighlight = tool.includes("highlight");
    const moments = (r.moments as Array<Record<string, unknown>>) ?? [];
    return moments
      .filter((m) => typeof m.t_start === "number" && typeof m.t_end === "number")
      .sort((a, b) => (typeof b.score === "number" ? b.score : 0) - (typeof a.score === "number" ? a.score : 0))
      .slice(0, 3)
      .map((m) => ({
        video_id: videoId,
        t_start: m.t_start as number,
        t_end: m.t_end as number,
        score: isHighlight ? undefined : (typeof m.score === "number" ? (m.score as number) : undefined),
        display_mode: "clip" as const,
      }));
  }

  const shots = (r.shots as Array<Record<string, unknown>>) ?? [];
  // group_by is the LLM-chosen presentation hint coming from the corpus search.
  // "video" → one result per distinct video; "clip" → keep all matched clips.
  const groupBy = r.group_by === "video" ? "video" : "clip";

  // Image-to-moment (find_scene_by_image): the user asked WHERE a scene is, not
  // what's being said — so don't surface the shot's (unrelated) ASR as a caption.
  // The card then shows just the thumbnail + clickable timestamp.
  const isScene = tool.includes("scene");
  const clips: ClipResult[] = shots
    .filter((s) => typeof s.t_start === "number" && typeof s.t_end === "number" && (s.t_end as number) - (s.t_start as number) >= 0.5)
    .map((s) => ({
      video_id: (s.video_id as string) ?? videoId,
      shot_idx: typeof s.idx === "number" ? (s.idx as number) : undefined,
      t_start: s.t_start as number,
      t_end: s.t_end as number,
      video_duration_s: typeof s.video_duration_s === "number" ? (s.video_duration_s as number) : undefined,
      original_filename: typeof s.original_filename === "string" ? (s.original_filename as string) : undefined,
      caption: isScene ? undefined : (typeof s.caption === "string" ? (s.caption as string) : (typeof s.asr_text === "string" ? (s.asr_text as string) : undefined)),
      // Image-to-moment results always seek to the matched moment's t_start — the
      // moment IS the answer, so never render them as a parent_video (plays from 0).
      display_mode: !isScene && groupBy === "video" ? "parent_video" : "clip",
    }));

  // Frontend fallback: for a CORPUS search that returned many shots of the SAME
  // video, collapse to one parent-video tile (the LLM should have grouped by
  // video). Only for corpus searches (no top-level video_id) — a single-video
  // search/scene (search_video_local, find_scene_by_image) OR any image-to-moment
  // scene search WANTS its moments shown as individual seekable cards, so never
  // collapse those (collapsing would lose the seek to the matched timestamp).
  if (clips.length > 1 && !videoId && !isScene) {
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

/**
 * Rebuild Turn[] from persisted messages. Messages are stored as strict
 * (user, assistant) pairs ordered by created_at asc. Thoughts are persisted
 * as per-chunk deltas → merge consecutive same-agent entries into one step.
 * tool_calls entries carry `result` (post 2026-06-10 backend) → replay them
 * through extractClips/extractSummary so old turns render the same cards as
 * live ones; result-less entries (older rows) render as bare tool_call steps.
 */
/** The video a turn actually acted on, read from its tool-call args/result.
 *  A turn can attach a different video than the conversation's pinned one
 *  (the user re-attaches mid-thread), so this is the source of truth for the
 *  per-turn attachment chip — NOT the single conversation.video_id. */
function turnActedVideoId(toolCalls: PersistedMessage["tool_calls"]): string | undefined {
  for (const tc of toolCalls ?? []) {
    const args = tc.args as Record<string, unknown> | undefined;
    const res = tc.result as Record<string, unknown> | undefined;
    const vid = (args?.video_id as string) ?? (res?.video_id as string);
    if (typeof vid === "string" && vid) return vid;
  }
  return undefined;
}

export function turnsFromMessages(
  messages: PersistedMessage[],
  fallbackVideoId?: string,
  fallbackVideoName?: string,
  videoNames: Record<string, string> = {},
): Turn[] {
  const turns: Turn[] = [];
  const blank = (): Turn => ({ user: "", attachments: [], assistant: "", steps: [], resultClips: [], summaries: [], edits: [] });
  // Per-message attachments aren't persisted, so reconstruct each turn's chip
  // from the video its tool calls acted on (below); only fall back to the
  // conversation's pinned video for turns with no per-video tool call.
  const turnAttachments = fallbackVideoId
    ? [{ id: fallbackVideoId, name: fallbackVideoName ?? "" }]
    : [];

  for (const m of messages) {
    if (m.role === "user") {
      turns.push({ ...blank(), user: m.content, image: m.image ?? undefined, attachments: turnAttachments });
      continue;
    }
    if (m.role !== "assistant") continue;
    let turn = turns[turns.length - 1];
    if (!turn || turn.assistant || turn.steps.length) {
      turn = blank();
      turns.push(turn);
    }

    const steps: ThinkingStep[] = [];
    for (const th of m.thoughts ?? []) {
      const agent = th.agent ?? "agent";
      const last = steps[steps.length - 1];
      if (last && last.type === "thought" && last.agent === agent) {
        last.text = (last.text ?? "") + (th.delta ?? "");
      } else {
        steps.push({ type: "thought", agent, text: th.delta ?? "" });
      }
    }

    const clips: ClipResult[] = [];
    const summaries: { videoId: string; text: string }[] = [];
    const edits: EditResult[] = [];
    for (const tc of m.tool_calls ?? []) {
      const tool = tc.tool ?? "";
      steps.push({ type: "tool_call", tool, args: tc.args });
      if (tc.result !== undefined && tc.result !== null) {
        steps.push({ type: "tool_result", tool, result: tc.result });
        clips.push(...extractClips(tool, tc.result));
        const s = extractSummary(tool, tc.result, fallbackVideoId ? [fallbackVideoId] : []);
        if (s) summaries.push(s);
        const e = extractEdit(tool, tc.result);
        if (e) edits.push(e);
      }
    }

    turn.assistant = m.content;
    turn.steps = steps;
    turn.resultClips = clips;
    turn.summaries = summaries;
    turn.edits = edits;

    // Override the chip with the video THIS turn actually acted on (it may differ
    // from the conversation's pinned video when the user re-attached mid-thread).
    const actedVid = turnActedVideoId(m.tool_calls);
    if (actedVid) {
      turn.attachments = [{ id: actedVid, name: videoNames[actedVid] ?? fallbackVideoName ?? "" }];
    }
  }
  return turns;
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

/** combine_clips produces ONE edited video (the concatenated clips). Surface it
 *  as a single playable card, NOT as the source moments. */
function extractEdit(tool: string, result: unknown): EditResult | null {
  if (!result || typeof result !== "object") return null;
  if (!(tool.includes("combine") || tool.includes("edit"))) return null;
  const r = result as Record<string, unknown>;
  const editId = r.edit_id as string;
  if (!editId) return null;
  const clips = Array.isArray(r.clips)
    ? (r.clips as Array<Record<string, unknown>>)
        .filter((c) => typeof c.t_start === "number" && typeof c.t_end === "number")
        .map((c) => ({ t_start: c.t_start as number, t_end: c.t_end as number }))
    : [];
  return { edit_id: editId, clips };
}

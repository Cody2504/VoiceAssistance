/**
 * SSE chat consumer — uses fetch+ReadableStream because EventSource doesn't support POST.
 *
 * Backend protocol (matches `/api/v1/chat/stream`):
 *   event: thought       data: {"agent":"planner","delta":"..."}
 *   event: tool_call     data: {"tool":"video-grounding","args":{...}}
 *   event: tool_result   data: {"tool":"video-grounding","result":{...}}
 *   event: message       data: {"delta":"..."}
 *   event: end           data: {"conversation_id":"...","message_id":"..."}
 */
import axios from "axios";

import { API_BASE_URL } from "@/config";
import { ROUTES, TOKEN_KEYS } from "@/constants/routes";

export type ChatEvent =
  | { type: "thought"; agent: string; delta: string }
  | { type: "tool_call"; tool: string; args: unknown }
  | { type: "tool_result"; tool: string; result: unknown }
  | { type: "message"; delta: string }
  | { type: "end"; conversation_id: string; message_id: string };

export interface ChatStreamInput {
  conversation_id?: string;
  video_id?: string;
  video_ids?: string[];
  index_id?: string;
  message: string;
  /** Optional base64 data-URL image attached to the turn (find_scene_by_image). */
  image?: string;
  signal?: AbortSignal;
  onEvent: (ev: ChatEvent) => void;
}

export async function streamChat({ conversation_id, video_id, video_ids, index_id, message, image, signal, onEvent }: ChatStreamInput) {
  const token = localStorage.getItem(TOKEN_KEYS.ACCESS);
  const res = await fetch(`${API_BASE_URL}${ROUTES.CHAT_STREAM}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ conversation_id, video_id, video_ids, index_id, message, image }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Chat stream failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalise CRLF → LF so the frame boundary is reliably `\n\n`
    // (sse-starlette emits CRLF per RFC, browsers/curl handle either).
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const ev = parseSseFrame(raw);
      if (ev) onEvent(ev);
    }
  }
}

function parseSseFrame(raw: string): ChatEvent | null {
  let eventType = "message";
  let dataStr = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) eventType = line.slice(6).trim();
    else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
  }
  if (!dataStr) return null;
  try {
    const data = JSON.parse(dataStr);
    if (eventType === "thought") return { type: "thought", agent: data.agent ?? "agent", delta: data.delta ?? data.text ?? "" };
    if (eventType === "tool_call") return { type: "tool_call", tool: data.tool, args: data.args };
    if (eventType === "tool_result") return { type: "tool_result", tool: data.tool, result: data.result };
    if (eventType === "message") return { type: "message", delta: data.delta ?? "" };
    if (eventType === "end") return { type: "end", conversation_id: data.conversation_id, message_id: data.message_id };
  } catch {
    /* fall through */
  }
  return null;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  video_id: string | null;
  created_at: string;
}

export interface PersistedMessage {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  thoughts: { agent?: string; delta?: string }[] | null;
  tool_calls: { tool?: string; args?: unknown; result?: unknown }[] | null;
  /** Base64 data-URL of an image attached to this user turn (null otherwise). */
  image?: string | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  video_id: string | null;
  messages: PersistedMessage[];
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const r = await axios.get(ROUTES.CONVERSATIONS);
  return r.data?.data ?? [];
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const r = await axios.get(ROUTES.CONVERSATION(id));
  return r.data?.data;
}

export async function deleteConversation(id: string): Promise<void> {
  await axios.delete(ROUTES.CONVERSATION(id));
}

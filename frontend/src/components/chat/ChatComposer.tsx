import { useState } from "react";
import { Plus, Send, Video as VideoIcon } from "lucide-react";

import type { VideoSummary } from "@/apis/videos.api";
import { AttachedVideoChip } from "./AttachedVideoChip";
import { cn } from "@/lib/utils";

interface Props {
  attached: VideoSummary[];
  onRemove: (videoId: string) => void;
  onSend: (message: string, videoIds: string[]) => void;
  onDropVideo: (video: VideoSummary) => void;
  busy?: boolean;
  placeholder?: string;
}

/**
 * Bottom composer matching the screenshots: video chips on top, big text input,
 * + attach button + Chat Mode pill on the bottom-left, send arrow on the bottom-right.
 * Accepts dropped video items (drag-and-drop from library).
 */
export function ChatComposer({ attached, onRemove, onSend, onDropVideo, busy, placeholder }: Props) {
  const [text, setText] = useState("");
  const [chatMode, setChatMode] = useState(true);
  const [dragOver, setDragOver] = useState(false);

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t, attached.map((v) => v.id));
    setText("");
  };

  return (
    <div
      onDragEnter={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const raw = e.dataTransfer.getData("application/x-video");
        if (raw) {
          try { onDropVideo(JSON.parse(raw) as VideoSummary); } catch { /* noop */ }
        }
      }}
      className={cn(
        "rounded-xl border bg-white shadow-sm transition",
        dragOver ? "border-neutral-900 ring-2 ring-neutral-200" : "border-neutral-200",
      )}
    >
      {attached.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-neutral-100 p-2">
          {attached.map((v) => (
            <AttachedVideoChip
              key={v.id}
              videoId={v.id}
              filename={v.original_filename}
              onRemove={() => onRemove(v.id)}
            />
          ))}
        </div>
      )}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
        }}
        rows={2}
        placeholder={placeholder ?? "Chat with your videos"}
        className="w-full resize-none rounded-t-xl border-0 px-4 pt-3 pb-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none"
      />

      <div className="flex items-center justify-between px-2 pb-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="rounded-full p-2 text-neutral-600 hover:bg-neutral-100"
            title="Attach (drag a video from the library or click here)"
          >
            <Plus size={16} />
          </button>
          <button
            type="button"
            onClick={() => setChatMode((m) => !m)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition",
              chatMode ? "bg-neutral-900 text-white" : "bg-neutral-100 text-neutral-700",
            )}
          >
            <VideoIcon size={12} />
            Chat Mode
          </button>
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={busy || !text.trim()}
          className="grid h-9 w-9 place-items-center rounded-full bg-neutral-900 text-white transition hover:bg-neutral-700 disabled:bg-neutral-200 disabled:text-neutral-400"
          aria-label="Send"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}

import { useRef, useState } from "react";
import { ImageIcon, Plus, Send, Video as VideoIcon, X } from "lucide-react";

import type { VideoSummary } from "@/apis/videos.api";
import { AttachedVideoChip } from "./AttachedVideoChip";
import { cn } from "@/lib/utils";

interface Props {
  attached: VideoSummary[];
  onRemove: (videoId: string) => void;
  onSend: (message: string, videoIds: string[], image?: string) => void;
  onDropVideo: (video: VideoSummary) => void;
  busy?: boolean;
  placeholder?: string;
}

/**
 * Bottom composer: video chips + an optional attached-image thumbnail on top, big
 * text input, attach/image buttons + Chat Mode pill on the bottom-left, send arrow
 * on the bottom-right. Accepts dropped video items (drag-and-drop from library).
 */
export function ChatComposer({ attached, onRemove, onSend, onDropVideo, busy, placeholder }: Props) {
  const [text, setText] = useState("");
  const [chatMode, setChatMode] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [image, setImage] = useState<{ dataUrl: string; name: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const pickImage = (file: File) => {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => setImage({ dataUrl: String(reader.result), name: file.name });
    reader.readAsDataURL(file);
  };

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t, attached.map((v) => v.id), image?.dataUrl);
    setText("");
    setImage(null);
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

      {/* attached image — shown in the box like the reference */}
      {image && (
        <div className="px-3 pt-3">
          <div className="group relative inline-block">
            <img
              src={image.dataUrl}
              alt={image.name}
              className="h-28 w-28 rounded-xl border border-neutral-200 object-cover"
            />
            <button
              type="button"
              onClick={() => setImage(null)}
              aria-label="Remove image"
              className="absolute -right-2 -top-2 grid h-6 w-6 place-items-center rounded-full bg-neutral-900 text-white shadow transition duration-150 ease-out hover:bg-neutral-700 active:scale-90 focus-visible:outline-2 focus-visible:outline-signal"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) pickImage(f);
          e.target.value = "";
        }}
      />

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
        }}
        rows={2}
        placeholder={placeholder ?? "Chat with your videos"}
        className="w-full resize-none border-0 px-4 pt-3 pb-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none"
      />

      <div className="flex items-center justify-between px-2 pb-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="rounded-full p-2 text-neutral-600 transition duration-150 ease-out hover:bg-neutral-100 active:scale-95"
            title="Attach (drag a video from the library here)"
          >
            <Plus size={16} />
          </button>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="rounded-full p-2 text-neutral-600 transition duration-150 ease-out hover:bg-neutral-100 active:scale-95 focus-visible:outline-2 focus-visible:outline-signal"
            title="Attach an image — ask Jockey to find the matching scene"
            aria-label="Attach image"
          >
            <ImageIcon size={16} />
          </button>
          <button
            type="button"
            onClick={() => setChatMode((m) => !m)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition duration-150 ease-out active:scale-[0.97]",
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
          className="grid h-9 w-9 place-items-center rounded-full bg-neutral-900 text-white transition duration-150 ease-out hover:bg-neutral-700 active:scale-95 disabled:bg-neutral-200 disabled:text-neutral-400 disabled:active:scale-100"
          aria-label="Send"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}

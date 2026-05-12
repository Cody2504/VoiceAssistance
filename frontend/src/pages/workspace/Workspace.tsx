import { useState } from "react";

import { LibraryGrid } from "@/components/library/LibraryGrid";
import { ChatThread } from "@/components/chat/ChatThread";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import type { VideoSummary } from "@/apis/videos.api";

/**
 * The default landing page: chat on the left (~60%), draggable library grid on the right.
 * Users drag videos from the right into the chat composer to attach them as context.
 */
export default function Workspace() {
  const [preview, setPreview] = useState<VideoSummary | null>(null);

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-0 divide-x divide-neutral-200">
      <section className="flex min-h-0 flex-col px-8 py-6">
        <header className="mb-2 flex items-center gap-2">
          <h1 className="text-base font-semibold">Jockey</h1>
          <span className="text-xs text-neutral-500">your video assistant</span>
        </header>
        <ChatThread />
      </section>

      <aside className="flex min-h-0 flex-col bg-neutral-50/40 p-4">
        <header className="mb-3">
          <h2 className="text-sm font-semibold">Your library</h2>
          <p className="text-xs text-neutral-500">Drag a video into the chat to ask about it.</p>
        </header>
        <LibraryGrid onPreview={(v) => setPreview(v)} />
      </aside>

      <VideoPreviewModal
        open={!!preview}
        videoId={preview?.id ?? null}
        onClose={() => setPreview(null)}
      />
    </div>
  );
}

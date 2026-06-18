import { useState } from "react";
import { useParams } from "react-router";
import { useTranslation } from "react-i18next";

import { LibraryGrid } from "@/components/library/LibraryGrid";
import { ChatThread } from "@/components/chat/ChatThread";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import type { VideoSummary } from "@/apis/videos.api";
import { ChatScopeBar, type ChatScopeValue } from "@/pages/chat/components/ChatScopeBar";

/**
 * The default landing page: chat on the left (~60%), draggable library grid on the right.
 * Users drag videos from the right into the chat composer to attach them as context.
 * The ChatScopeBar above the thread lets users widen scope to an Index (whole or subset)
 * so cross-video questions can run.
 */
export default function Workspace() {
  const { t } = useTranslation();
  const { conversationId } = useParams<{ conversationId: string }>();
  const [preview, setPreview] = useState<VideoSummary | null>(null);
  const [scope, setScope] = useState<ChatScopeValue>({ mode: "single", videoIds: [] });

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-0 divide-x divide-neutral-200 overflow-hidden">
      <section className="flex min-h-0 flex-col px-8 py-6">
        <div className="shrink-0">
          <ChatScopeBar value={scope} onChange={setScope} />
        </div>
        <div className="min-h-0 flex-1">
          <ChatThread scope={scope} conversationId={conversationId} />
        </div>
      </section>

      <aside className="flex min-h-0 flex-col bg-neutral-50/40 p-4">
        <header className="mb-3 shrink-0">
          <h2 className="text-sm font-semibold">{t("console.workspace.library_title")}</h2>
          <p className="text-xs text-neutral-500">{t("console.workspace.library_hint")}</p>
        </header>
        <div className="min-h-0 flex-1">
          <LibraryGrid onPreview={(v) => setPreview(v)} />
        </div>
      </aside>

      <VideoPreviewModal
        open={!!preview}
        videoId={preview?.id ?? null}
        onClose={() => setPreview(null)}
      />
    </div>
  );
}

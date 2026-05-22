import { useState } from "react";

import { LibraryGrid } from "@/components/library/LibraryGrid";
import { VideoPreviewModal } from "@/components/video/VideoPreviewModal";
import type { VideoSummary } from "@/apis/videos.api";

/**
 * Playground: Library — manage indexed videos.
 *
 * Single-column layout (no examples panel — a video list doesn't have example
 * queries). Delegates entirely to LibraryGrid for upload + grid + delete,
 * adds page chrome + a preview modal on click.
 */
export default function Library() {
  const [preview, setPreview] = useState<VideoSummary | null>(null);

  return (
    <div className="h-full overflow-y-auto bg-neutral-50/40">
      <div className="mx-auto max-w-6xl px-8 py-8">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Library</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Upload videos to make them searchable. Indexing runs automatically — videos appear here
            once they're ready.
          </p>
        </header>

        <div className="rounded-lg border border-neutral-200 bg-white p-4">
          <LibraryGrid onPreview={setPreview} />
        </div>
      </div>

      <VideoPreviewModal
        open={preview != null}
        videoId={preview?.id ?? null}
        onClose={() => setPreview(null)}
      />
    </div>
  );
}

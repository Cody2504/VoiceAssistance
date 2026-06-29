import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { VideoThumb } from "@/components/video/VideoThumb";
import { linkifyTimestamps, seekMarkdownComponents } from "./timestampLink";

interface Props {
  videoId: string;
  text: string;
  onPreview: () => void;
  /** Seek the card's video to `sec` when a [mm:ss] citation chip is clicked. */
  onSeek?: (sec: number) => void;
}

/**
 * Side-by-side thumbnail + description, matching the "summarize each video" screenshot.
 * Inline [mm:ss-mm:ss] citations render as click-to-seek chips.
 */
export function VideoSummaryCard({ videoId, text, onPreview, onSeek }: Props) {
  return (
    <div className="grid grid-cols-[280px_1fr] items-start gap-4 py-2">
      <VideoThumb videoId={videoId} onClick={onPreview} className="aspect-video" />
      <div className="text-sm leading-relaxed text-neutral-800 [&_p]:my-1">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={seekMarkdownComponents(onSeek)}>
          {linkifyTimestamps(text)}
        </ReactMarkdown>
      </div>
    </div>
  );
}

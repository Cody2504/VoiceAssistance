import { VideoThumb } from "@/components/video/VideoThumb";

interface Props {
  videoId: string;
  text: string;
  onPreview: () => void;
}

/**
 * Side-by-side thumbnail + description, matching the "summarize each video" screenshot.
 */
export function VideoSummaryCard({ videoId, text, onPreview }: Props) {
  return (
    <div className="grid grid-cols-[280px_1fr] items-start gap-4 py-2">
      <VideoThumb videoId={videoId} onClick={onPreview} className="aspect-video" />
      <p className="text-sm leading-relaxed text-neutral-800">{text}</p>
    </div>
  );
}

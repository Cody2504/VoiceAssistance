import { X } from "lucide-react";
import { VideoThumb } from "@/components/video/VideoThumb";

interface Props {
  videoId: string;
  filename: string;
  onRemove: () => void;
}

export function AttachedVideoChip({ videoId, filename, onRemove }: Props) {
  const short = filename.length > 12 ? `${filename.slice(0, 10)}…` : filename;
  return (
    <div className="inline-flex items-center gap-2 rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs shadow-sm">
      <VideoThumb videoId={videoId} className="h-7 w-12 rounded" />
      <span className="text-neutral-700">{short}</span>
      <button onClick={onRemove} className="rounded p-0.5 text-neutral-500 hover:bg-neutral-100" type="button" aria-label="Remove">
        <X size={12} />
      </button>
    </div>
  );
}

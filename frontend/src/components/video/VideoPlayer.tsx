import { forwardRef, useImperativeHandle, useRef } from "react";

export interface VideoPlayerHandle {
  seekTo: (seconds: number) => void;
  play: () => void;
  pause: () => void;
}

interface Props {
  src: string;
  onTimeUpdate?: (t: number) => void;
}

export const VideoPlayer = forwardRef<VideoPlayerHandle, Props>(function VideoPlayer({ src, onTimeUpdate }, ref) {
  const el = useRef<HTMLVideoElement>(null);

  useImperativeHandle(ref, () => ({
    seekTo: (s: number) => { if (el.current) { el.current.currentTime = s; el.current.play().catch(() => {}); } },
    play: () => { el.current?.play().catch(() => {}); },
    pause: () => { el.current?.pause(); },
  }), []);

  return (
    <video
      ref={el}
      src={src}
      controls
      onTimeUpdate={(e) => onTimeUpdate?.((e.target as HTMLVideoElement).currentTime)}
      className="aspect-video w-full overflow-hidden rounded-lg bg-black"
    />
  );
});

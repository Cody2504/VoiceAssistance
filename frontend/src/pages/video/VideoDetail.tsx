import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { GroundingTimeline } from "@/components/video/GroundingTimeline";
import { VideoPlayer, type VideoPlayerHandle } from "@/components/video/VideoPlayer";
import {
  askVideo, getStreamUrl, groundVideo, searchVideo,
  type GroundResponse, type VideoSummary,
} from "@/apis/videos.api";
import { useVideoStatus } from "@/hooks/useVideoStatus";
import { formatSeconds } from "@/lib/utils";

type Tab = "ground" | "search" | "qa";

export default function VideoDetail() {
  const { videoId } = useParams<{ videoId: string }>();
  const video = useVideoStatus(videoId);
  const [streamUrl, setStreamUrl] = useState("");
  const [tab, setTab] = useState<Tab>("ground");
  const [grounding, setGrounding] = useState<GroundResponse | undefined>();
  const player = useRef<VideoPlayerHandle>(null);

  useEffect(() => {
    if (videoId && video?.status === "ready") {
      getStreamUrl(videoId).then(setStreamUrl).catch(() => toast.error("Failed to load video"));
    }
  }, [videoId, video?.status]);

  const seek = (t: number) => player.current?.seekTo(t);

  return (
    <div className="grid h-full grid-cols-[1.6fr_1fr] gap-6 p-6">
      <div className="flex min-h-0 flex-col gap-3">
        <VideoStatusBanner video={video} />
        {streamUrl && (
          <VideoPlayer ref={player} src={streamUrl} />
        )}
        <GroundingTimeline
          duration={video?.duration_s ?? 0}
          result={grounding}
          onSeek={seek}
        />
      </div>

      <Card className="flex min-h-0 flex-col">
        <div className="mb-3 flex gap-1 border-b border-neutral-100 pb-2 text-xs">
          {(["ground", "search", "qa"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded px-3 py-1 transition ${tab === t ? "bg-neutral-100 text-neutral-900" : "text-neutral-500 hover:text-neutral-800"}`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1">
          {tab === "ground" && videoId && (
            <DirectQueryPanel
              label="Run trained grounding head"
              onRun={async (q) => setGrounding(await groundVideo(videoId, q))}
              renderResult={grounding ? () => (
                <div className="space-y-1 text-xs">
                  {grounding.shots.map((s) => (
                    <button
                      key={s.idx}
                      onClick={() => seek(s.t_start)}
                      className="block w-full rounded border border-neutral-100 bg-white p-2 text-left hover:bg-neutral-50"
                    >
                      <span className="font-mono">{formatSeconds(s.t_start)}–{formatSeconds(s.t_end)}</span>
                      {" · "}rel={(s.relevance ?? 0).toFixed(2)}
                      {s.asr_text && <p className="text-neutral-500">{s.asr_text}</p>}
                    </button>
                  ))}
                </div>
              ) : undefined}
            />
          )}
          {tab === "search" && videoId && (
            <DirectQueryPanel
              label="Qdrant similarity search"
              onRun={async (q) => { const r = await searchVideo(videoId, q); toast.info(`${r.shots.length} hits`); return r; }}
            />
          )}
          {tab === "qa" && videoId && (
            <DirectQueryPanel
              label="Ask a question about the video"
              onRun={async (q) => askVideo(videoId, q)}
            />
          )}
        </div>
      </Card>
    </div>
  );
}

function VideoStatusBanner({ video }: { video?: VideoSummary }) {
  if (!video) return null;
  if (video.status === "ready") return null;
  return (
    <div className="rounded-md border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-600">
      Status: <span className="font-mono">{video.status}</span>
      {video.error && <span className="ml-2 text-red-600">{video.error}</span>}
    </div>
  );
}

function DirectQueryPanel({
  label, onRun, renderResult,
}: {
  label: string;
  onRun: (q: string) => Promise<unknown>;
  renderResult?: () => React.ReactNode;
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<unknown>();

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    try { setOut(await onRun(q)); }
    catch (err) { toast.error((err as Error).message || "Request failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="flex h-full flex-col">
      <form onSubmit={run} className="mb-3 flex gap-2">
        <Input placeholder={label} value={q} onChange={(e) => setQ(e.target.value)} disabled={busy} />
        <Button type="submit" disabled={busy || !q.trim()}>Run</Button>
      </form>
      <div className="min-h-0 flex-1 overflow-auto">
        {renderResult ? renderResult() : (
          out !== undefined && <pre className="text-xs text-neutral-600">{JSON.stringify(out, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}

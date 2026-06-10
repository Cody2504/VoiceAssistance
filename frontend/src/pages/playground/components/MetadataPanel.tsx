import { Play } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { SegmentTrack, TrackSegment } from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

import type { SegmentPresetMeta } from "../data/presets";

interface Props {
  tracks: SegmentTrack[];
  presetById: Record<string, SegmentPresetMeta>;
  activeByTrack: Record<string, TrackSegment | null>;
  onSeek: (t: number) => void;
}

function findSegmentIndex(track: SegmentTrack, active: TrackSegment | null) {
  if (!active) return -1;
  return track.segments.findIndex(
    (s) => s.t_start === active.t_start && s.t_end === active.t_end,
  );
}

export function MetadataPanel({ tracks, presetById, activeByTrack, onSeek }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-bold text-neutral-700">{t("pgkit.metadata.title")}</p>
      {tracks.map((track) => {
        const preset = presetById[track.definition_id];
        const active = activeByTrack[track.definition_id] ?? null;
        const idx = findSegmentIndex(track, active);
        const color = preset?.color ?? { fill: "#E5E5E5", stroke: "#404040" };
        const isActive = !!active;
        return (
          <div
            key={track.definition_id}
            className={`rounded-[20px] border bg-neutral-100 transition-[background-color,border-color] duration-300 ${isActive ? "bg-neutral-200" : ""}`}
            style={{ borderColor: isActive ? color.stroke : "transparent" }}
          >
            <div className="flex flex-wrap items-center gap-x-2 px-6 pt-6 pb-3">
              <div className="flex min-w-0 flex-1 items-center gap-1">
                <div
                  className="h-3 w-3 shrink-0 rounded border"
                  style={{ backgroundColor: color.fill, borderColor: color.stroke }}
                />
                <p
                  className="truncate font-mono text-[13px] font-medium text-neutral-600"
                  title={track.definition_id}
                >
                  {track.definition_id}
                </p>
              </div>
              {isActive && active && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onSeek(active.t_start)}
                    className="inline-flex items-center gap-1 rounded-md border border-neutral-800 px-1.5 py-0.5 font-mono text-[11px] text-neutral-800 hover:bg-neutral-100"
                  >
                    <Play size={12} />
                    {formatSeconds(active.t_start)}–{formatSeconds(active.t_end)}
                  </button>
                  <span className="rounded-md border border-neutral-800 px-1.5 py-0.5 font-mono text-[11px] text-neutral-800">
                    {idx + 1}/{track.segments.length}
                  </span>
                </div>
              )}
            </div>

            <div className="px-6 pb-6 pl-10">
              {!track.implemented && (
                <p className="font-mono text-[11px] text-neutral-400">
                  {t("pgkit.metadata.not_implemented")}
                </p>
              )}
              {track.implemented && !active && (
                <p className="font-mono text-[11px] text-neutral-400">
                  {t("pgkit.metadata.no_active_segment")}
                </p>
              )}
              {track.implemented && active && (
                <div className="flex flex-col gap-2">
                  {Object.entries(active.metadata).length === 0 && (
                    <p className="font-mono text-[11px] text-neutral-400">
                      {t("pgkit.metadata.no_fields")}
                    </p>
                  )}
                  {Object.entries(active.metadata).map(([k, v]) => (
                    <div key={k} className="flex flex-col gap-0.5">
                      <span className="font-mono text-[11px] font-medium text-neutral-600">
                        {k}
                      </span>
                      <span className="break-words text-sm text-neutral-900">
                        {v === null || v === undefined || v === ""
                          ? "—"
                          : typeof v === "object"
                          ? JSON.stringify(v)
                          : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

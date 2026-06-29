import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Scissors } from "lucide-react";

import { getEditStreamUrl } from "@/apis/videos.api";
import { formatSeconds } from "@/lib/utils";

export interface EditResult {
  edit_id: string;
  clips: { t_start: number; t_end: number }[];
}

/**
 * The single combined video produced by `combine_clips` (cut + concatenate).
 * Plays the edit inline — a fresh presigned URL is fetched by `edit_id` so it
 * survives reload (the /edit URL expires in ~1h). Below the player, the source
 * ranges that were stitched together are listed for reference.
 */
export function EditedClipCard({ edit }: { edit: EditResult }) {
  const { t } = useTranslation();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    getEditStreamUrl(edit.edit_id)
      .then((u) => alive && setUrl(u))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [edit.edit_id]);

  return (
    <div className="space-y-2 rounded-lg border border-neutral-200 p-3">
      <div className="flex items-center gap-1.5 text-sm font-medium text-neutral-800">
        <Scissors size={14} className="text-emerald-600" />
        {t("chat.edited_clip.title", "Combined clip")}
        <span className="font-normal text-neutral-500">
          · {t("chat.edited_clip.segments", "{{count}} segments", { count: edit.clips.length })}
        </span>
      </div>
      {url ? (
        <video src={url} controls className="aspect-video w-full rounded-md bg-black" />
      ) : (
        <div className="grid aspect-video w-full place-items-center rounded-md bg-neutral-100 text-sm text-neutral-400">
          {failed ? t("chat.edited_clip.unavailable", "Clip unavailable") : t("console.preview.loading")}
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {edit.clips.map((c, i) => (
          <span key={i} className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs tabular-nums text-neutral-600">
            {formatSeconds(c.t_start)}–{formatSeconds(c.t_end)}
          </span>
        ))}
      </div>
    </div>
  );
}

import { useRef, useState } from "react";
import { ArrowUpFromLine } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

interface Props {
  onFiles: (files: File[]) => void;
  className?: string;
}

const ACCEPT = "video/*,.mp4,.mov,.webm,.mkv";

function pickVideos(files: FileList): File[] {
  return Array.from(files).filter(
    (f) => f.type.startsWith("video/") || /\.(mp4|mov|webm|mkv)$/i.test(f.name),
  );
}

/** TwelveLabs-style upload zone: warm gradient card, dashed inner border,
 *  "Drop videos or browse files" + constraint chips. Click anywhere to browse. */
export function VideoDropZone({ onFiles, className }: Props) {
  const { t } = useTranslation();
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const chips = [
    t("console.index_drop.chip_duration"),
    t("console.index_drop.chip_resolution"),
    t("console.index_drop.chip_ratio"),
    t("console.index_drop.chip_size"),
  ];

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => fileRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        if (!dragOver) setDragOver(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const list = pickVideos(e.dataTransfer.files);
        if (list.length) onFiles(list);
      }}
      className={cn(
        "cursor-pointer overflow-hidden rounded-[20px] bg-gradient-warm p-4 transition",
        className,
      )}
    >
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) {
            const list = pickVideos(e.target.files);
            if (list.length) onFiles(list);
          }
          e.target.value = "";
        }}
      />
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-[14px] border border-dashed px-6 py-14 transition-colors",
          dragOver ? "border-[var(--color-obsidian)]" : "border-[var(--color-gravel)]/40",
        )}
      >
        <ArrowUpFromLine size={20} className="text-[var(--color-obsidian)]" />
        <p className="text-[16px] text-[var(--color-obsidian)]">{t("console.index_drop.label")}</p>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
          {chips.map((c) => (
            <span
              key={c}
              className="rounded-md border border-[var(--color-gravel)]/40 bg-white/60 px-2 py-0.5 text-[11px] text-[var(--color-obsidian)]"
            >
              {c}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

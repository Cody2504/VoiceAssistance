import { useTranslation } from "react-i18next";

/**
 * The "real-looking" Jockey result preview shown on the hero.
 * Static — no real data. Demonstrates: query bar, four frames (two matched), scrubber with three segments, caption.
 */
export function ProductChip() {
  const { t } = useTranslation();
  return (
    <div className="w-full max-w-[420px] rounded-[var(--radius-lg)] border border-black/5 bg-white p-4 shadow-[0_24px_60px_rgba(0,0,0,0.10)]">
      {/* query bar */}
      <div className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
        <span className="rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">Q</span>
        <span className="truncate">{t("landing.hero.chip_query")}</span>
      </div>

      {/* frame thumbnails */}
      <div className="mt-3 grid grid-cols-4 gap-1.5">
        {[
          { ts: "00:12", match: false },
          { ts: "02:14", match: true },
          { ts: "04:01", match: false },
          { ts: "06:45", match: true },
        ].map((f) => (
          <div
            key={f.ts}
            className="relative aspect-[16/10] rounded"
            style={{
              background: f.match
                ? "linear-gradient(135deg, #2a1a44, #1c1024)"
                : "linear-gradient(135deg, #f0eada, #e0d4f0)",
              boxShadow: f.match ? "0 0 0 2px var(--accent)" : "none",
            }}
          >
            <span
              className="absolute bottom-1 left-1 text-[9px] font-mono"
              style={{ color: f.match ? "#ffd9ff" : "#888" }}
            >
              {f.ts}
            </span>
          </div>
        ))}
      </div>

      {/* scrubber */}
      <div className="mt-3 h-3 rounded bg-[#f3f0ea]">
        <div className="relative h-full">
          <span className="absolute top-0 bottom-0" style={{ left: "18%", width: "14%", background: "linear-gradient(90deg, #ff8caa, #7a4dff)", opacity: 0.75, borderRadius: 3 }} />
          <span className="absolute top-0 bottom-0" style={{ left: "56%", width: "8%",  background: "linear-gradient(90deg, #ff8caa, #7a4dff)", opacity: 0.75, borderRadius: 3 }} />
          <span className="absolute top-0 bottom-0" style={{ left: "78%", width: "10%", background: "linear-gradient(90deg, #ff8caa, #7a4dff)", opacity: 0.75, borderRadius: 3 }} />
        </div>
      </div>

      <p className="mt-2 text-[11px] text-[var(--ink-muted)]">{t("landing.hero.chip_caption")}</p>
    </div>
  );
}

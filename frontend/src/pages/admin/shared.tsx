/** Small shared pieces for the admin pages — byte formatting and the CSS bar
 * list used for the 30-day series (no chart library, matches the usage-meter
 * style used elsewhere in the console). */

export function fmtBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
}

export function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
      <p className="text-[12px] font-medium uppercase tracking-[0.1em] text-[var(--color-gravel)]">{label}</p>
      <p className="mt-2 text-[26px] font-semibold tracking-[-0.4px] text-[var(--color-obsidian)]">{value}</p>
      {sub && <p className="mt-0.5 text-[12px] text-[var(--color-gravel)]">{sub}</p>}
    </div>
  );
}

export function BarList({
  rows,
  emptyLabel,
}: {
  rows: { label: string; value: number; display: string }[];
  emptyLabel: string;
}) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  if (!rows.length) return <p className="text-[13px] text-[var(--color-gravel)]">{emptyLabel}</p>;
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-3 text-[12px]">
          <span className="w-14 shrink-0 text-[var(--color-gravel)]">{r.label}</span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[var(--color-chalk)]">
            <div className="h-full rounded-full bg-[#5fb364]" style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
          <span className="w-20 shrink-0 text-right text-[var(--color-obsidian)]">{r.display}</span>
        </div>
      ))}
    </div>
  );
}

/** "2026-06-10" → "Jun 10" style short label for bar rows. */
export function shortDay(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Build a continuous, zero-filled daily series for the last `days` days
 * (anchored to today) from sparse {day, value} points. */
export function dailySeries(
  points: { day: string; value: number }[],
  days: number,
): { day: string; value: number }[] {
  const byDay = new Map(points.map((p) => [p.day.slice(0, 10), p.value]));
  const out: { day: string; value: number }[] = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    out.push({ day: iso, value: byDay.get(iso) ?? 0 });
  }
  return out;
}

/** Vertical bar chart (CSS only, no chart lib). The tallest bar is highlighted
 * (accent colour + its value printed on top), the rest are muted — matching the
 * reference dashboard. Each column has a hover tooltip. Keep the row count small
 * (≈5–7) so the x-axis labels stay readable. */
export function BarChart({
  rows,
  emptyLabel,
  accent = "#6366f1",
}: {
  rows: { label: string; value: number; display: string }[];
  emptyLabel: string;
  accent?: string;
}) {
  if (!rows.length) return <p className="text-[13px] text-[var(--color-gravel)]">{emptyLabel}</p>;
  const max = Math.max(...rows.map((r) => r.value), 1);
  const peak = rows.reduce((mi, r, i, a) => (r.value > a[mi].value ? i : mi), 0);
  return (
    <div className="flex h-44 items-stretch gap-2">
      {rows.map((r, i) => {
        const hl = i === peak && r.value > 0;
        return (
          <div key={i} className="flex flex-1 flex-col" title={`${r.label}: ${r.display}`}>
            <div className="flex flex-1 flex-col items-center justify-end">
              {hl && <span className="mb-1 text-[11px] font-semibold text-[var(--color-obsidian)]">{r.display}</span>}
              <div
                className="w-full rounded-md transition-all"
                style={{
                  height: `${Math.max((r.value / max) * 100, r.value > 0 ? 6 : 2)}%`,
                  background: hl ? accent : "var(--color-chalk)",
                }}
              />
            </div>
            <span className="mt-1.5 truncate text-center text-[10px] text-[var(--color-gravel)]">{r.label}</span>
          </div>
        );
      })}
    </div>
  );
}

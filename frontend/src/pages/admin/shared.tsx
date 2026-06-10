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

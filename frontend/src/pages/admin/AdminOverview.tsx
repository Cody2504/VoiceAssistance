import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAdminStatsQuery } from "@/apis/queries";
import { formatUSD } from "@/pages/pricing/pricingData";
import { BarChart, StatCard, dailySeries, fmtBytes, shortDay } from "./shared";

// Build a small, readable series: Week = last 7 days (weekday labels); Month =
// the last 5 weeks aggregated into weekly buckets (so the x-axis stays legible).
function buildSeries(points: { day: string; value: number }[], range: "week" | "month") {
  if (range === "week") {
    return dailySeries(points, 7).map((d) => ({
      label: new Date(d.day + "T00:00:00").toLocaleDateString("en-US", { weekday: "short" }),
      value: d.value,
    }));
  }
  const daily = dailySeries(points, 35);
  const out: { label: string; value: number }[] = [];
  for (let w = 0; w < 5; w++) {
    const slice = daily.slice(w * 7, w * 7 + 7);
    out.push({ label: shortDay(slice[0].day), value: slice.reduce((a, d) => a + d.value, 0) });
  }
  return out;
}

// Only Stripe is wired up today; the rest are on the roadmap.
const INTEGRATIONS: { name: string; type: string; status: "active" | "soon" }[] = [
  { name: "Stripe", type: "Payments", status: "active" },
  { name: "VNPay", type: "Payments", status: "soon" },
  { name: "Zapier", type: "Automation", status: "soon" },
  { name: "Shopify", type: "Commerce", status: "soon" },
];

export default function AdminOverview() {
  const { t } = useTranslation();
  const { data: stats, isError } = useAdminStatsQuery();
  const [range, setRange] = useState<"week" | "month">("week");

  if (isError) {
    return <div className="p-8 text-sm text-[var(--color-gravel)]">{t("admin.overview.error")}</div>;
  }
  if (!stats) return null;

  const signupRows = buildSeries(
    stats.signups_daily.map((d) => ({ day: d.day, value: d.count })),
    range,
  ).map((b) => ({ ...b, display: String(b.value) }));
  const costRows = buildSeries(
    stats.cost_daily.map((d) => ({ day: d.day, value: d.cost_usd })),
    range,
  ).map((b) => ({ ...b, display: formatUSD(b.value) }));

  const planEntries = Object.entries(stats.users_per_plan);
  const paidSubs = planEntries
    .filter(([p]) => p !== "free")
    .reduce((a, [, n]) => a + n, 0);
  const totalUsers = planEntries.reduce((a, [, n]) => a + n, 0) || 1;

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-8">
      <h1 className="text-[26px] font-semibold tracking-[-0.4px]">{t("admin.overview.title")}</h1>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("admin.overview.users")} value={String(stats.users)} />
        <StatCard label={t("admin.overview.subscriptions")} value={String(paidSubs)} sub={t("admin.overview.paid_plans")} />
        <StatCard label={t("admin.overview.storage")} value={fmtBytes(stats.storage_bytes)} />
        <StatCard
          label={t("admin.overview.spend_30d")}
          value={formatUSD(stats.cost_usd_30d)}
          sub={`${t("admin.overview.spend_total")}: ${formatUSD(stats.cost_usd_total)}`}
        />
      </div>

      <div className="mt-6 flex items-center justify-end">
        <div className="inline-flex overflow-hidden rounded-lg border border-[var(--color-chalk)] text-[12px]">
          {(["week", "month"] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              className={
                range === r
                  ? "bg-[var(--color-obsidian)] px-3 py-1 text-white"
                  : "px-3 py-1 text-[var(--color-gravel)] hover:bg-[var(--color-eggshell)]"
              }
            >
              {t(`admin.overview.range_${r}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-2 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
          <h2 className="mb-4 text-[14px] font-semibold">{t("admin.overview.signups")}</h2>
          <BarChart emptyLabel={t("admin.overview.no_data")} rows={signupRows} accent="#6366f1" />
        </section>
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
          <h2 className="mb-4 text-[14px] font-semibold">{t("admin.overview.cost")}</h2>
          <BarChart emptyLabel={t("admin.overview.no_data")} rows={costRows} accent="#0447ff" />
        </section>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Subscriptions / plan distribution */}
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
          <h2 className="mb-4 text-[14px] font-semibold">{t("admin.overview.subscriptions")}</h2>
          <div className="space-y-3">
            {planEntries.map(([plan, n]) => (
              <div key={plan} className="text-[13px]">
                <div className="mb-1 flex justify-between">
                  <span className="capitalize">{plan}</span>
                  <span className="text-[var(--color-gravel)]">{n}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[var(--color-chalk)]">
                  <div className="h-full rounded-full bg-[#6366f1]" style={{ width: `${(n / totalUsers) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* List of Integration */}
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
          <h2 className="mb-4 text-[14px] font-semibold">{t("admin.overview.integrations")}</h2>
          <table className="w-full text-left text-[13px]">
            <thead className="text-[var(--color-gravel)]">
              <tr>
                <th className="py-1.5 font-medium">{t("admin.overview.int_app")}</th>
                <th className="py-1.5 font-medium">{t("admin.overview.int_type")}</th>
                <th className="py-1.5 text-right font-medium">{t("admin.overview.int_status")}</th>
              </tr>
            </thead>
            <tbody>
              {INTEGRATIONS.map((it) => (
                <tr key={it.name} className="border-t border-[var(--color-chalk)]/60">
                  <td className="py-2 font-medium">{it.name}</td>
                  <td className="py-2 text-[var(--color-gravel)]">{it.type}</td>
                  <td className="py-2 text-right">
                    <span
                      className={
                        it.status === "active"
                          ? "rounded-full bg-[#3e7e45]/10 px-2 py-0.5 text-[11px] font-medium text-[#3e7e45]"
                          : "rounded-full bg-[var(--color-chalk)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-gravel)]"
                      }
                    >
                      {it.status === "active" ? t("admin.overview.int_active") : t("admin.overview.int_soon")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

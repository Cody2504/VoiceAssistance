import { useTranslation } from "react-i18next";

import { useAdminStatsQuery } from "@/apis/queries";
import { formatUSD } from "@/pages/pricing/pricingData";
import { BarList, StatCard, fmtBytes, shortDay } from "./shared";

export default function AdminOverview() {
  const { t } = useTranslation();
  const { data: stats, isError } = useAdminStatsQuery();

  if (isError) {
    return <div className="p-8 text-sm text-[var(--color-gravel)]">{t("admin.overview.error")}</div>;
  }
  if (!stats) return null;

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-8">
      <h1 className="text-[26px] font-semibold tracking-[-0.4px]">{t("admin.overview.title")}</h1>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("admin.overview.users")}
          value={String(stats.users)}
        />
        <StatCard
          label={t("admin.overview.videos")}
          value={String(stats.videos)}
          sub={t("admin.overview.video_minutes", { count: Math.round(stats.video_minutes) })}
        />
        <StatCard label={t("admin.overview.storage")} value={fmtBytes(stats.storage_bytes)} />
        <StatCard
          label={t("admin.overview.spend_30d")}
          value={formatUSD(stats.cost_usd_30d)}
          sub={`${t("admin.overview.spend_total")}: ${formatUSD(stats.cost_usd_total)}`}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
          <h2 className="mb-4 text-[14px] font-semibold">{t("admin.overview.signups")}</h2>
          <BarList
            emptyLabel={t("admin.overview.no_data")}
            rows={stats.signups_daily.map((d) => ({
              label: shortDay(d.day),
              value: d.count,
              display: String(d.count),
            }))}
          />
        </section>
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
          <h2 className="mb-4 text-[14px] font-semibold">{t("admin.overview.cost")}</h2>
          <BarList
            emptyLabel={t("admin.overview.no_data")}
            rows={stats.cost_daily.map((d) => ({
              label: shortDay(d.day),
              value: d.cost_usd,
              display: formatUSD(d.cost_usd),
            }))}
          />
        </section>
      </div>

      <section className="mt-6 rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
        <h2 className="mb-3 text-[14px] font-semibold">{t("admin.overview.per_plan")}</h2>
        <table className="w-full text-left text-[13px]">
          <thead className="text-[var(--color-gravel)]">
            <tr>
              <th className="py-1.5 font-medium">{t("admin.overview.col_plan")}</th>
              <th className="py-1.5 font-medium">{t("admin.overview.col_users")}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(stats.users_per_plan).map(([plan, n]) => (
              <tr key={plan} className="border-t border-[var(--color-chalk)]/60">
                <td className="py-1.5 capitalize">{plan}</td>
                <td className="py-1.5">{n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

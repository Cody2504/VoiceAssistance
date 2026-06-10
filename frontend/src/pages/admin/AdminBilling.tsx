import { useTranslation } from "react-i18next";

import { useAdminPlansQuery, useAdminStatsQuery } from "@/apis/queries";

export default function AdminBilling() {
  const { t } = useTranslation();
  const { data: plans, isError } = useAdminPlansQuery();
  const { data: stats } = useAdminStatsQuery();

  if (isError) {
    return <div className="p-8 text-sm text-[var(--color-gravel)]">{t("admin.billing.error")}</div>;
  }

  const quota = (n: number | null) => (n === null ? t("admin.billing.unlimited") : n.toLocaleString());

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-8">
      <h1 className="text-[26px] font-semibold tracking-[-0.4px]">{t("admin.billing.title")}</h1>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--color-chalk)] bg-white">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-[var(--color-eggshell)] text-[var(--color-gravel)]">
            <tr>
              <th className="px-4 py-2.5 font-medium">{t("admin.billing.col_plan")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.billing.col_index")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.billing.col_search")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.billing.col_ground")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.billing.col_qa")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.billing.col_summary")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.billing.col_users")}</th>
            </tr>
          </thead>
          <tbody>
            {(plans ?? []).map((p) => (
              <tr key={p.id} className="border-t border-[var(--color-chalk)]/60">
                <td className="px-4 py-2.5 font-medium">{p.name}</td>
                <td className="px-3 py-2.5">{quota(p.monthly_index_minutes)}</td>
                <td className="px-3 py-2.5">{quota(p.monthly_search_queries)}</td>
                <td className="px-3 py-2.5">{quota(p.monthly_ground_calls)}</td>
                <td className="px-3 py-2.5">{quota(p.monthly_qa_calls)}</td>
                <td className="px-3 py-2.5">{quota(p.monthly_summary_calls)}</td>
                <td className="px-3 py-2.5">{stats?.users_per_plan?.[p.id] ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

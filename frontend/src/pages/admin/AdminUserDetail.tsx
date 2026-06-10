import { useState } from "react";
import { Link, useParams } from "react-router";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import { setUserPlan } from "@/apis/admin.api";
import { useAdminPlansQuery, useAdminUserQuery } from "@/apis/queries";
import { formatUSD } from "@/pages/pricing/pricingData";
import { BarList, StatCard, fmtBytes, shortDay } from "./shared";

export default function AdminUserDetail() {
  const { t } = useTranslation();
  const { userId } = useParams<{ userId: string }>();
  const queryClient = useQueryClient();
  const { data: u, isError } = useAdminUserQuery(userId);
  const { data: plans } = useAdminPlansQuery();
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function changePlan(planId: string) {
    if (!userId || !planId) return;
    setSaving(true);
    setNote(null);
    try {
      await setUserPlan(userId, planId);
      await queryClient.invalidateQueries({ queryKey: ["admin-user", userId] });
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      setNote(t("admin.user_detail.plan_updated"));
    } catch {
      setNote(t("admin.user_detail.update_failed"));
    } finally {
      setSaving(false);
    }
  }

  if (isError) {
    return <div className="p-8 text-sm text-[var(--color-gravel)]">{t("admin.user_detail.error")}</div>;
  }
  if (!u) return null;

  const none = t("admin.user_detail.none");

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-8">
      <Link
        to="/admin/users"
        className="inline-flex items-center gap-1.5 text-[13px] text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]"
      >
        <ArrowLeft size={14} />
        {t("admin.user_detail.back")}
      </Link>
      <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.4px]">{u.email}</h1>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {/* profile */}
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5 text-[13px]">
          <h2 className="mb-3 text-[14px] font-semibold">{t("admin.user_detail.profile")}</h2>
          <dl className="space-y-2">
            <Row k={t("admin.user_detail.email")} v={u.email} />
            <Row k={t("admin.user_detail.role")} v={u.role} />
            <Row
              k={t("admin.user_detail.status")}
              v={u.is_active ? t("admin.users.active") : t("admin.users.suspended")}
            />
            <Row k={t("admin.user_detail.joined")} v={new Date(u.created_at).toLocaleDateString()} />
          </dl>
        </section>

        {/* subscription + plan override */}
        <section className="rounded-2xl border border-[var(--color-chalk)] bg-white p-5 text-[13px]">
          <h2 className="mb-3 text-[14px] font-semibold">{t("admin.user_detail.subscription")}</h2>
          <dl className="space-y-2">
            <div className="flex items-center justify-between">
              <dt className="text-[var(--color-gravel)]">{t("admin.user_detail.plan")}</dt>
              <dd>
                <select
                  value={u.plan_id}
                  disabled={saving || !plans}
                  onChange={(e) => void changePlan(e.target.value)}
                  className="cursor-pointer rounded-lg border border-[var(--color-chalk)] bg-white px-2 py-1 text-[13px]"
                >
                  {(plans ?? [{ id: u.plan_id, name: u.plan_id }]).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </dd>
            </div>
            <Row k={t("admin.user_detail.sub_status")} v={u.sub_status ?? none} />
            <Row
              k={t("admin.user_detail.period_end")}
              v={u.current_period_end ? new Date(u.current_period_end).toLocaleDateString() : none}
            />
            <Row k={t("admin.user_detail.stripe_customer")} v={u.stripe_customer_id ?? none} />
          </dl>
          {note && <p className="mt-3 text-[12px] text-[var(--color-gravel)]">{note}</p>}
        </section>
      </div>

      {/* usage stats */}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("admin.user_detail.videos")} value={String(u.video_count)} />
        <StatCard
          label={t("admin.user_detail.storage")}
          value={fmtBytes(u.storage_bytes)}
          sub={t("admin.user_detail.minutes", { count: Math.round(u.duration_s / 60) })}
        />
        <StatCard label={t("admin.user_detail.conversations")} value={String(u.conversation_count)} />
        <StatCard label={t("admin.user_detail.spend_30d")} value={formatUSD(u.cost_usd_30d)} />
      </div>

      <section className="mt-4 rounded-2xl border border-[var(--color-chalk)] bg-white p-5">
        <h2 className="mb-4 text-[14px] font-semibold">{t("admin.user_detail.cost_daily")}</h2>
        <BarList
          emptyLabel={t("admin.user_detail.no_usage")}
          rows={u.usage_daily.map((d) => ({
            label: shortDay(d.day),
            value: d.cost_usd,
            display: formatUSD(d.cost_usd),
          }))}
        />
      </section>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-[var(--color-gravel)]">{k}</dt>
      <dd className="text-[var(--color-obsidian)]">{v}</dd>
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";

import { updatePlan, type AdminPlan } from "@/apis/admin.api";
import { useAdminPlansQuery, useAdminStatsQuery, qk } from "@/apis/queries";

const LIMIT_FIELDS = [
  "monthly_index_minutes",
  "monthly_search_queries",
  "monthly_ground_calls",
  "monthly_qa_calls",
  "monthly_summary_calls",
] as const;

type LimitField = (typeof LIMIT_FIELDS)[number];

export default function AdminBilling() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data: plans, isError } = useAdminPlansQuery();
  const { data: stats } = useAdminStatsQuery();
  const [editing, setEditing] = useState<AdminPlan | null>(null);

  if (isError) {
    return <div className="p-8 text-sm text-[var(--color-gravel)]">{t("admin.billing.error")}</div>;
  }

  const quota = (n: number | null) => (n === null ? t("admin.billing.unlimited") : n.toLocaleString());
  const labelFor: Record<LimitField, string> = {
    monthly_index_minutes: t("admin.billing.col_index"),
    monthly_search_queries: t("admin.billing.col_search"),
    monthly_ground_calls: t("admin.billing.col_ground"),
    monthly_qa_calls: t("admin.billing.col_qa"),
    monthly_summary_calls: t("admin.billing.col_summary"),
  };

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-8">
      <h1 className="text-[26px] font-semibold tracking-[-0.4px]">{t("admin.billing.title")}</h1>
      <p className="mt-1 text-[13px] text-[var(--color-gravel)]">{t("admin.billing.edit_hint")}</p>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--color-chalk)] bg-white">
        <table className="w-full whitespace-nowrap text-left text-[13px]">
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
              <tr
                key={p.id}
                onClick={() => setEditing(p)}
                className="cursor-pointer border-t border-[var(--color-chalk)]/60 transition hover:bg-[var(--color-powder)]/50"
              >
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

      {editing && (
        <PlanEditModal
          plan={editing}
          labelFor={labelFor}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await queryClient.invalidateQueries({ queryKey: qk.adminPlans() });
          }}
        />
      )}
    </div>
  );
}

function PlanEditModal({
  plan,
  labelFor,
  onClose,
  onSaved,
}: {
  plan: AdminPlan;
  labelFor: Record<LimitField, string>;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(plan.name);
  // "" means unlimited (null); otherwise the numeric string.
  const [limits, setLimits] = useState<Record<LimitField, string>>(
    () =>
      Object.fromEntries(
        LIMIT_FIELDS.map((f) => [f, plan[f] === null ? "" : String(plan[f])]),
      ) as Record<LimitField, string>,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  async function save() {
    setSaving(true);
    setError(false);
    try {
      const body: Record<string, unknown> = { name };
      for (const f of LIMIT_FIELDS) {
        const raw = limits[f].trim();
        body[f] = raw === "" ? null : Number(raw);
      }
      await updatePlan(plan.id, body);
      await onSaved();
    } catch {
      setError(true);
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-[18px] font-semibold">{t("admin.billing.edit_title", { plan: plan.name })}</h2>
        <p className="mt-1 text-[12px] text-[var(--color-gravel)]">{t("admin.billing.unlimited_hint")}</p>

        <label className="mt-4 block text-[12px] font-medium text-[var(--color-gravel)]">
          {t("admin.billing.field_name")}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--color-chalk)] px-3 py-2 text-[13px] text-[var(--color-obsidian)]"
          />
        </label>

        <div className="mt-3 grid grid-cols-2 gap-3">
          {LIMIT_FIELDS.map((f) => (
            <label key={f} className="block text-[12px] font-medium text-[var(--color-gravel)]">
              {labelFor[f]}
              <input
                type="number"
                min={0}
                value={limits[f]}
                placeholder={t("admin.billing.unlimited")}
                onChange={(e) => setLimits((s) => ({ ...s, [f]: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-[var(--color-chalk)] px-3 py-2 text-[13px] text-[var(--color-obsidian)]"
              />
            </label>
          ))}
        </div>

        {error && <p className="mt-3 text-[12px] text-red-600">{t("admin.billing.save_error")}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--color-chalk)] px-4 py-2 text-[13px]"
          >
            {t("admin.billing.cancel")}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-[var(--color-obsidian)] px-4 py-2 text-[13px] text-white disabled:opacity-40"
          >
            {saving ? t("admin.billing.saving") : t("admin.billing.save")}
          </button>
        </div>
      </div>
    </div>
  );
}

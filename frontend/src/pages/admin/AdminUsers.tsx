import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, ShieldOff, Lock, LockOpen } from "lucide-react";

import { patchAdminUser, type AdminUserRow } from "@/apis/admin.api";
import { useAdminUsersQuery } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import { formatUSD } from "@/pages/pricing/pricingData";
import { cn } from "@/lib/utils";
import { fmtBytes } from "./shared";

export default function AdminUsers() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user: me } = useAuth();
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { data, isError } = useAdminUsersQuery(search, page);

  // Debounce typing → search param (resets to page 1).
  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(input.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(id);
  }, [input]);

  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));

  async function act(u: AdminUserRow, patch: { role?: "user" | "admin"; is_active?: boolean }, confirmKey: string) {
    if (!window.confirm(t(confirmKey, { email: u.email }))) return;
    try {
      await patchAdminUser(u.id, patch);
    } catch {
      window.alert(t("admin.users.action_failed"));
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-user", u.id] });
  }

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-8">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-[26px] font-semibold tracking-[-0.4px]">{t("admin.users.title")}</h1>
        <span className="text-[13px] text-[var(--color-gravel)]">
          {t("admin.users.total", { count: data?.total ?? 0 })}
        </span>
      </div>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={t("admin.users.search_placeholder")}
        className="mt-4 h-10 w-full max-w-sm rounded-xl border border-[var(--color-chalk)] bg-white px-3 text-[13px] outline-none placeholder:text-[var(--color-gravel)]/70 focus:border-[var(--color-accent-blue)]"
      />

      {isError && <p className="mt-6 text-sm text-[var(--color-gravel)]">{t("admin.users.error")}</p>}

      <div className="mt-4 overflow-x-auto rounded-2xl border border-[var(--color-chalk)] bg-white">
        <table className="w-full text-left text-[13px]">
          <thead className="whitespace-nowrap bg-[var(--color-eggshell)] text-[var(--color-gravel)]">
            <tr>
              <th className="px-4 py-2.5 font-medium">{t("admin.users.col_email")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_role")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_plan")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_status")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_videos")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_storage")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_spend")}</th>
              <th className="px-3 py-2.5 font-medium">{t("admin.users.col_joined")}</th>
              <th className="px-3 py-2.5 text-center font-medium">{t("admin.users.col_permission")}</th>
              <th className="px-3 py-2.5 text-center font-medium">{t("admin.users.col_lock")}</th>
            </tr>
          </thead>
          <tbody className="whitespace-nowrap">
            {(data?.items ?? []).map((u) => {
              const isMe = u.id === me?.id;
              return (
                <tr
                  key={u.id}
                  onClick={() => navigate(`/admin/users/${u.id}`)}
                  className="cursor-pointer border-t border-[var(--color-chalk)]/60 transition hover:bg-[var(--color-powder)]/50"
                >
                  <td className="px-4 py-2.5">
                    {u.email}
                    {isMe && (
                      <span className="ml-2 rounded-full bg-[var(--color-chalk)] px-1.5 py-0.5 text-[10px]">
                        {t("admin.users.you")}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[11px] font-medium",
                        u.role === "admin" ? "bg-[#0447ff]/10 text-[#0447ff]" : "bg-[var(--color-chalk)] text-[var(--color-gravel)]"
                      )}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 capitalize">{u.plan_id}</td>
                  <td className="px-3 py-2.5">
                    <span className={cn("text-[12px]", u.is_active ? "text-[#3e7e45]" : "text-red-600")}>
                      {u.is_active ? t("admin.users.active") : t("admin.users.suspended")}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">{u.video_count}</td>
                  <td className="px-3 py-2.5">{fmtBytes(u.storage_bytes)}</td>
                  <td className="px-3 py-2.5">{formatUSD(u.cost_usd_30d)}</td>
                  <td className="px-3 py-2.5 text-[var(--color-gravel)]">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                    {!isMe && (
                      <button
                        type="button"
                        title={u.role === "admin" ? t("admin.users.demote") : t("admin.users.promote")}
                        className="inline-flex cursor-pointer text-[var(--color-accent-blue)] hover:opacity-70"
                        onClick={() =>
                          u.role === "admin"
                            ? void act(u, { role: "user" }, "admin.users.confirm_demote")
                            : void act(u, { role: "admin" }, "admin.users.confirm_promote")
                        }
                      >
                        {u.role === "admin" ? <ShieldOff size={18} strokeWidth={1.75} /> : <ShieldCheck size={18} strokeWidth={1.75} />}
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                    {!isMe && (
                      <button
                        type="button"
                        title={u.is_active ? t("admin.users.suspend") : t("admin.users.reactivate")}
                        className={cn("inline-flex cursor-pointer hover:opacity-70", u.is_active ? "text-red-600" : "text-[#3e7e45]")}
                        onClick={() =>
                          u.is_active
                            ? void act(u, { is_active: false }, "admin.users.confirm_suspend")
                            : void act(u, { is_active: true }, "admin.users.confirm_reactivate")
                        }
                      >
                        {u.is_active ? <Lock size={18} strokeWidth={1.75} /> : <LockOpen size={18} strokeWidth={1.75} />}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-[var(--color-gravel)]">
                  {t("admin.users.empty")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-[13px] text-[var(--color-gravel)]">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="cursor-pointer rounded-lg border border-[var(--color-chalk)] bg-white px-3 py-1.5 disabled:opacity-40"
          >
            {t("admin.users.prev")}
          </button>
          <span>{t("admin.users.page_of", { page, pages })}</span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
            className="cursor-pointer rounded-lg border border-[var(--color-chalk)] bg-white px-3 py-1.5 disabled:opacity-40"
          >
            {t("admin.users.next")}
          </button>
        </div>
      )}
    </div>
  );
}

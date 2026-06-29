import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Info, ArrowUpRight, MessageSquare, Check, Loader2, AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getSubscription, getInvoices, startCheckout, type Subscription, type Invoice } from "@/apis/billing.api";
import { getMyUsage, getIndexUsage } from "@/apis/usage.api";
import { formatUSD } from "@/pages/pricing/pricingData";

/**
 * Billing & plan page — wired to the billing-service.
 *   - Reads the user's real subscription (plan / status / renewal) from
 *     GET /api/v1/billing/subscription, defaulting to the seeded Free plan.
 *   - "Upgrade plan" / "Register payment method" start a Stripe Checkout Session
 *     (POST /api/v1/billing/checkout) and redirect to Stripe's hosted page; the
 *     plan flips to Developer once Stripe's webhook lands.
 *   - Usage cost rollup comes from the token-usage service (GET /usage/me).
 *   - Demo only: everything runs in Stripe TEST mode (test cards, no real money).
 */

function capLabel(minutes: number | null | undefined, unlimited: string): string {
  if (minutes == null) return unlimited;
  return minutes >= 60 ? `${+(minutes / 60).toFixed(1)} hr` : `${minutes} min`;
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-[#e6f4ea] text-[#137333]",
  trialing: "bg-[#e8f0fe] text-[#1a73e8]",
  past_due: "bg-[#fce8e6] text-[#c5221f]",
  canceled: "bg-[var(--color-chalk)] text-[var(--color-slate)]",
  incomplete: "bg-[#fef7e0] text-[#b06000]",
};

export default function BillingPlan() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [usageCost, setUsageCost] = useState<number>(0);
  const [usedMinutes, setUsedMinutes] = useState<number>(0);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);

  const checkoutFlag = params.get("checkout"); // "success" | "cancelled" | null

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, u, iu, inv] = await Promise.allSettled([
        getSubscription(), getMyUsage(), getIndexUsage(), getInvoices(),
      ]);
      if (s.status === "fulfilled") setSub(s.value);
      else throw s.reason;
      if (u.status === "fulfilled") {
        setUsageCost(u.value.days.reduce((acc, d) => acc + (d.cost_usd || 0), 0));
      }
      if (iu.status === "fulfilled") setUsedMinutes(iu.value.used_minutes || 0);
      if (inv.status === "fulfilled") setInvoices(inv.value);
    } catch {
      setError(t("settings.billing.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  // Clear the ?checkout= flag from the URL after we've shown the banner once.
  useEffect(() => {
    if (!checkoutFlag) return;
    const timer = setTimeout(() => {
      params.delete("checkout");
      setParams(params, { replace: true });
    }, 6000);
    return () => clearTimeout(timer);
  }, [checkoutFlag, params, setParams]);

  const onUpgrade = useCallback(async () => {
    setRedirecting(true);
    try {
      await startCheckout(); // navigates away to Stripe on success
    } catch {
      setError(t("settings.billing.error_checkout"));
      setRedirecting(false);
    }
  }, [t]);

  const planName = sub?.plan?.name ?? (sub?.plan_id ? sub.plan_id : "Free");
  const isFree = (sub?.plan_id ?? "free") === "free";
  const isPaid = !isFree && sub?.status !== "canceled";
  const indexCap = sub?.plan?.monthly_index_minutes ?? null;
  const renewal = sub?.current_period_end
    ? new Date(sub.current_period_end).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
    : null;

  const unlimited = t("settings.billing.unlimited");

  if (loading) {
    return (
      <Section>
        <div className="flex items-center gap-2 text-[var(--color-slate)]">
          <Loader2 size={16} className="animate-spin" /> {t("settings.billing.loading")}
        </div>
      </Section>
    );
  }

  return (
    <>
      {checkoutFlag === "success" && (
        <Banner tone="success" icon={<Check size={16} />}>
          {t("settings.billing.banner_success_pre")} <b>Developer</b> {t("settings.billing.banner_success_post")}
        </Banner>
      )}
      {checkoutFlag === "cancelled" && (
        <Banner tone="neutral" icon={<Info size={16} />}>
          {t("settings.billing.banner_cancelled")}
        </Banner>
      )}
      {error && (
        <Banner tone="error" icon={<AlertCircle size={16} />}>
          {error}
        </Banner>
      )}

      {/* Plan card */}
      <Section>
        <div className="flex items-center justify-between gap-12">
          <div className="flex flex-1 items-center gap-3">
            <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
              {t("settings.billing.plan_label", { name: planName })}
            </p>
            {sub?.status && (
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium capitalize ${
                  STATUS_STYLE[sub.status] ?? "bg-[var(--color-chalk)] text-[var(--color-slate)]"
                }`}
              >
                {sub.status.replace("_", " ")}
              </span>
            )}
          </div>
          <a
            href="mailto:hello@jockey.local"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--color-obsidian)] hover:underline"
          >
            <MessageSquare size={16} /> {t("settings.billing.talk_to_sales")}
          </a>
          <a
            href="/pricing"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--color-obsidian)] hover:underline"
          >
            {t("settings.billing.pricing")} <ArrowUpRight size={14} />
          </a>
        </div>

        <Label label={t("settings.billing.video_usage")} />
        <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
          {capLabel(usedMinutes, unlimited)}
          <span className="text-[var(--color-slate)]"> / {capLabel(indexCap, unlimited)}</span>
        </p>

        <div className="flex w-[550px] max-w-full flex-col gap-2">
          <div className="relative flex h-3 w-full items-center overflow-hidden rounded border border-[var(--color-obsidian)]">
            <span
              className="inline-block h-full"
              style={{ width: `${indexCap ? Math.min(100, (usedMinutes / indexCap) * 100) : 0}%` }}
            >
              <div className="h-full w-full bg-[#5fb364]" />
            </span>
          </div>
          <div className="flex items-center gap-3 text-[12px] text-[var(--color-obsidian)]">
            <span className="inline-flex items-center gap-1">
              <span aria-hidden className="inline-block h-2 w-2 rounded-[2px] border border-[var(--color-slate)] bg-[#5fb364]" />
              {t("settings.billing.indexing")}
            </span>
          </div>
        </div>

        <div className="flex gap-10">
          <div className="flex flex-col gap-2">
            <Label label={t("settings.billing.max_duration")} />
            <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
              {capLabel(indexCap, unlimited)}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label label={t("settings.billing.search_queries")} />
            <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
              {sub?.plan?.monthly_search_queries == null ? unlimited : `${sub.plan.monthly_search_queries}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          {isPaid ? (
            <span className="inline-flex h-10 items-center gap-1.5 rounded-[12px] bg-[#e6f4ea] px-[18px] text-[14px] font-medium text-[#137333]">
              <Check size={16} /> {t("settings.billing.on_plan", { name: planName })}
            </span>
          ) : (
            <button
              type="button"
              onClick={onUpgrade}
              disabled={redirecting}
              className="inline-flex h-10 items-center gap-1 rounded-[12px] bg-[var(--color-obsidian)] px-[18px] text-[14px] font-medium text-white transition-all duration-200 ease-out hover:rounded-[16px] hover:bg-neutral-800 active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
            >
              {redirecting ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> {t("settings.billing.redirecting")}
                </>
              ) : (
                <>
                  {t("settings.billing.upgrade")} <ArrowUpRight size={14} />
                </>
              )}
            </button>
          )}
          {renewal && (
            <span className="text-[13px] text-[var(--color-slate)]">
              {t("settings.billing.renews", { date: renewal })}
            </span>
          )}
        </div>
      </Section>

      {/* Payment */}
      <Section>
        <SectionTitle>{t("settings.billing.payment_title")}</SectionTitle>
        <p className="-mt-2 text-[13px] text-[var(--color-gravel)]">
          {t("settings.billing.payment_desc")}
        </p>
        <button
          type="button"
          onClick={onUpgrade}
          disabled={redirecting}
          className="inline-flex h-10 w-fit items-center gap-1 rounded-[12px] border border-[var(--color-obsidian)] bg-transparent px-[18px] text-[14px] font-medium text-[var(--color-obsidian)] transition-all duration-200 ease-out hover:rounded-[16px] hover:bg-black/5 active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
        >
          {isPaid ? t("settings.billing.update_payment") : t("settings.billing.register_payment")}
        </button>
      </Section>

      {/* Total amount due (grey background) */}
      <Section grey>
        <SectionTitle>{t("settings.billing.amount_due")}</SectionTitle>
        <div className="flex gap-20">
          <Stat label={t("settings.billing.usage_charges")} value={formatUSD(usageCost)} />
          <Stat
            label={t("settings.billing.plan_stat")}
            value={isPaid ? t("settings.billing.recurring", { name: planName }) : planName}
          />
          <Stat
            label={isPaid ? t("settings.billing.renewal_date") : t("settings.billing.charge_date")}
            value={renewal ?? "—"}
          />
        </div>
      </Section>

      {/* Billing history */}
      <Section>
        <SectionTitle>{t("settings.billing.history_title")}</SectionTitle>
        <div className="overflow-hidden rounded-xl">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--color-chalk)] text-left">
                {(
                  [
                    "col_issued",
                    "col_due",
                    "col_status",
                    "col_total",
                    "col_paid",
                    "col_period",
                    "col_invoice",
                    "col_receipt",
                    "col_usage",
                  ] as const
                ).map((colKey, i) => (
                  <th
                    key={colKey}
                    className={`whitespace-nowrap px-3 py-3 font-semibold text-[var(--color-obsidian)] ${i >= 6 ? "text-center" : "text-left"}`}
                  >
                    {t(`settings.billing.${colKey}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {invoices.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-10 text-center text-[var(--color-gravel)]">
                    {t("settings.billing.no_history")}
                  </td>
                </tr>
              ) : (
                invoices.map((inv, i) => (
                  <tr key={i} className="border-b border-[var(--color-chalk)] last:border-0">
                    <td className="whitespace-nowrap px-3 py-3">{new Date(inv.issued_at).toLocaleDateString()}</td>
                    <td className="whitespace-nowrap px-3 py-3">{new Date(inv.due_at).toLocaleDateString()}</td>
                    <td className="px-3 py-3">
                      <span className="rounded-full bg-[#e7f6e9] px-2 py-0.5 text-[11px] font-medium capitalize text-[#3f9a48]">
                        {inv.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">{formatUSD(inv.total)}</td>
                    <td className="whitespace-nowrap px-3 py-3">{formatUSD(inv.amount_paid)}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-[var(--color-gravel)]">
                      {new Date(inv.period_start).toLocaleDateString()} – {new Date(inv.period_end).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-3 text-center text-[var(--color-gravel)]">—</td>
                    <td className="px-3 py-3 text-center text-[var(--color-gravel)]">—</td>
                    <td className="px-3 py-3 text-center text-[var(--color-gravel)]">{inv.usage_summary}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

function Banner({
  children,
  tone,
  icon,
}: {
  children: React.ReactNode;
  tone: "success" | "error" | "neutral";
  icon: React.ReactNode;
}) {
  const toneClass =
    tone === "success"
      ? "border-[#a8dab5] bg-[#e6f4ea] text-[#137333]"
      : tone === "error"
        ? "border-[#f5c6c2] bg-[#fce8e6] text-[#c5221f]"
        : "border-[var(--color-chalk)] bg-[var(--color-powder)] text-[var(--color-obsidian)]";
  return (
    <div className={`flex items-start gap-2 rounded-[16px] border px-5 py-3.5 text-[13px] ${toneClass}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <p className="leading-relaxed">{children}</p>
    </div>
  );
}

function Section({ children, grey }: { children: React.ReactNode; grey?: boolean }) {
  return (
    <section
      className={`flex w-full flex-col gap-6 rounded-[32px] border border-[var(--color-chalk)] p-9 ${
        grey ? "bg-[var(--color-powder)]" : "bg-white"
      }`}
    >
      {children}
    </section>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[18px] leading-8 text-[var(--color-obsidian)]">{children}</p>
  );
}

function Label({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1">
      <p className="text-[13px] text-[var(--color-gravel)]">{label}</p>
      <Info size={14} className="text-[var(--color-slate)]" />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-2">
      <Label label={label} />
      <p className="text-[14px] text-[var(--color-obsidian)]">{value}</p>
    </div>
  );
}

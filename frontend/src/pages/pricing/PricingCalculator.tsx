import { useMemo, useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, ArrowLeft, Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  FAMILIES,
  ITEMS,
  computeDeveloperCost,
  formatUSD,
  type FamilyId,
} from "./pricingData";

const HORSE_GLYPH = (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
    <path d="M19 6c0-.55-.45-1-1-1h-2l-1-1H9L8 5H6c-.55 0-1 .45-1 1v.5c0 1.66 1.34 3 3 3h.5l-.5 2-3 1.5L3 14v3l3.5-.5L9 14h.5l.5 1.5L9 19h2l1.5-3 1.5 3h2l-1-3.5.5-1.5h3l-.5-2 .5-2c1.1 0 2-.9 2-2V6z" />
  </svg>
);

// Inputs the calculator collects. Distinct from internal billing units —
// indexing is collected as hours but billed by minute, etc.
type CalcInputs = {
  indexHours: number;
  searchQueries: number;
  groundCalls: number;
  qaCalls: number;
  summarizeCalls: number;
  months: number;
};

const DEFAULTS: CalcInputs = {
  indexHours: 10,
  searchQueries: 1000,
  groundCalls: 200,
  qaCalls: 500,
  summarizeCalls: 25,
  months: 1,
};

function NumberField({
  label,
  hint,
  value,
  onChange,
  step = 1,
  min = 0,
  suffix,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  suffix?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-6 py-4">
      <div className="min-w-0">
        <div className="text-sm font-medium text-[var(--ink)]">{label}</div>
        <div className="mt-0.5 text-xs text-[var(--ink-muted)]">{hint}</div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <input
          type="number"
          min={min}
          step={step}
          value={value}
          onChange={(e) => {
            const n = Number(e.target.value);
            onChange(Number.isFinite(n) ? Math.max(min, n) : min);
          }}
          className="w-28 rounded-lg border border-[var(--line)] bg-white px-3 py-1.5 text-right text-sm focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
        />
        {suffix && <span className="text-xs text-[var(--ink-muted)]">{suffix}</span>}
      </div>
    </div>
  );
}

function CostRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div
      className={`flex items-baseline justify-between border-t border-[var(--line)] py-3 text-sm ${
        accent ? "font-semibold text-[var(--ink)]" : "text-[var(--ink-soft)]"
      }`}
    >
      <span>{label}</span>
      <span className={accent ? "font-semibold" : "font-medium text-[var(--ink)]"}>{value}</span>
    </div>
  );
}

function FamilyHeader({ id }: { id: FamilyId }) {
  const f = FAMILIES[id];
  return (
    <div className="flex items-center gap-2">
      <span className="text-[var(--ink-soft)]">{HORSE_GLYPH}</span>
      <span className="text-sm font-semibold text-[var(--ink)]">{f.name}</span>
    </div>
  );
}

export default function PricingCalculator() {
  const { t } = useTranslation();
  const [inputs, setInputs] = useState<CalcInputs>(DEFAULTS);

  // Map UI inputs onto the billing units used in pricingData.ts.
  const usage = useMemo(
    () => ({
      index: inputs.indexHours * 60,        // hours → minutes
      search: inputs.searchQueries / 1000,  // queries → 1K-query units
      ground: inputs.groundCalls,
      qa: inputs.qaCalls,
      summarize: inputs.summarizeCalls,
    }),
    [inputs],
  );

  const cost = useMemo(() => computeDeveloperCost(usage), [usage]);
  const monthlyTotal = cost.total;
  const projectedTotal = monthlyTotal * inputs.months;

  const itemRows = ITEMS.map((item) => ({
    item,
    cost: cost.byItem[item.id] ?? 0,
  }));

  const indexItem = ITEMS.find(i => i.id === "index");

  return (
    <main className="mx-auto max-w-6xl px-6 pb-24 pt-12 md:pt-16">
      <Link
        to="/pricing"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--ink-soft)] transition hover:text-[var(--ink)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        {t("marketing.pricing_calc.back")}
      </Link>

      <header className="fade-rise mt-6 text-center">
        <h1 className="text-[40px] font-semibold tracking-[-0.02em] md:text-[56px]">
          {t("marketing.pricing_calc.heading")}
        </h1>
        <p className="mx-auto mt-4 max-w-[52ch] text-sm text-[var(--ink-soft)] md:text-base">
          {t("marketing.pricing_calc.sub")}
        </p>
      </header>

      <div className="mt-12 grid gap-8 md:grid-cols-[1.3fr_1fr]">
        {/* LEFT: inputs */}
        <div className="space-y-8">
          {/* Eclipse */}
          <section className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <FamilyHeader id="eclipse" />
            <p className="mt-1 text-xs text-[var(--ink-muted)]">{t("marketing.pricing_calc.eclipse_sub")}</p>

            <div className="mt-4 divide-y divide-[var(--line)]">
              <NumberField
                label={t("marketing.pricing_calc.field_index_label")}
                hint={`$${indexItem?.developerRate}/min`}
                value={inputs.indexHours}
                onChange={(v) => setInputs((s) => ({ ...s, indexHours: v }))}
                min={0}
                step={1}
                suffix={t("marketing.pricing_calc.field_index_suffix")}
              />
              <NumberField
                label={t("marketing.pricing_calc.field_search_label")}
                hint={t("marketing.pricing_calc.field_search_hint")}
                value={inputs.searchQueries}
                onChange={(v) => setInputs((s) => ({ ...s, searchQueries: v }))}
                min={0}
                step={100}
                suffix={t("marketing.pricing_calc.field_search_suffix")}
              />
              <NumberField
                label={t("marketing.pricing_calc.field_ground_label")}
                hint={t("marketing.pricing_calc.field_ground_hint")}
                value={inputs.groundCalls}
                onChange={(v) => setInputs((s) => ({ ...s, groundCalls: v }))}
                min={0}
                step={10}
                suffix={t("marketing.pricing_calc.field_ground_suffix")}
              />
            </div>
          </section>

          {/* Secretariat */}
          <section className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <FamilyHeader id="secretariat" />
            <p className="mt-1 text-xs text-[var(--ink-muted)]">{t("marketing.pricing_calc.secretariat_sub")}</p>

            <div className="mt-4 divide-y divide-[var(--line)]">
              <NumberField
                label={t("marketing.pricing_calc.field_qa_label")}
                hint={t("marketing.pricing_calc.field_qa_hint")}
                value={inputs.qaCalls}
                onChange={(v) => setInputs((s) => ({ ...s, qaCalls: v }))}
                min={0}
                step={10}
                suffix={t("marketing.pricing_calc.field_qa_suffix")}
              />
              <NumberField
                label={t("marketing.pricing_calc.field_summarize_label")}
                hint={t("marketing.pricing_calc.field_summarize_hint")}
                value={inputs.summarizeCalls}
                onChange={(v) => setInputs((s) => ({ ...s, summarizeCalls: v }))}
                min={0}
                step={5}
                suffix={t("marketing.pricing_calc.field_summarize_suffix")}
              />
            </div>
          </section>

          <section className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-[var(--ink)]">{t("marketing.pricing_calc.projection_title")}</div>
                <div className="mt-0.5 text-xs text-[var(--ink-muted)]">
                  {t("marketing.pricing_calc.projection_hint")}
                </div>
              </div>
              <select
                value={inputs.months}
                onChange={(e) => setInputs((s) => ({ ...s, months: Number(e.target.value) }))}
                className="rounded-lg border border-[var(--line)] bg-white px-3 py-1.5 text-sm focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
              >
                {[1, 3, 6, 12].map((m) => (
                  <option key={m} value={m}>
                    {m} {m > 1 ? t("marketing.pricing_calc.month_plural") : t("marketing.pricing_calc.month_singular")}
                  </option>
                ))}
              </select>
            </div>
          </section>
        </div>

        {/* RIGHT: live cost summary, sticky */}
        <aside>
          <div className="sticky top-20 rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <div className="text-lg font-semibold text-[var(--ink)]">{t("marketing.pricing_calc.cost_summary")}</div>
            <p className="mt-0.5 text-xs text-[var(--ink-muted)]">
              {t("marketing.pricing_calc.cost_summary_sub")}
            </p>

            {/* Eclipse subtotal */}
            <div className="mt-5">
              <FamilyHeader id="eclipse" />
              <div className="mt-1">
                {itemRows
                  .filter(({ item }) => item.family === "eclipse")
                  .map(({ item, cost }) => (
                    <CostRow key={item.id} label={t(item.labelKey)} value={formatUSD(cost)} />
                  ))}
                <CostRow label={t("marketing.pricing_calc.eclipse_subtotal")} value={formatUSD(cost.byFamily.eclipse)} accent />
              </div>
            </div>

            {/* Secretariat subtotal */}
            <div className="mt-7">
              <FamilyHeader id="secretariat" />
              <div className="mt-1">
                {itemRows
                  .filter(({ item }) => item.family === "secretariat")
                  .map(({ item, cost }) => (
                    <CostRow key={item.id} label={t(item.labelKey)} value={formatUSD(cost)} />
                  ))}
                <CostRow
                  label={t("marketing.pricing_calc.secretariat_subtotal")}
                  value={formatUSD(cost.byFamily.secretariat)}
                  accent
                />
              </div>
            </div>

            {/* Total */}
            <div className="mt-7 rounded-2xl bg-[var(--bg)] p-5">
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-[var(--ink-soft)]">{t("marketing.pricing_calc.monthly_total")}</span>
                <span className="text-2xl font-semibold tracking-tight">
                  {formatUSD(monthlyTotal)}
                </span>
              </div>
              {inputs.months > 1 && (
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-xs text-[var(--ink-muted)]">
                    {t("marketing.pricing_calc.projected", { months: inputs.months })}
                  </span>
                  <span className="text-sm font-medium text-[var(--ink)]">
                    {formatUSD(projectedTotal)}
                  </span>
                </div>
              )}
            </div>

            {/* CTA */}
            <div className="mt-6">
              <div className="text-sm font-semibold text-[var(--ink)]">{t("marketing.pricing_calc.start_free_heading")}</div>
              <p className="mt-1 text-xs text-[var(--ink-muted)]">
                {t("marketing.pricing_calc.start_free_body")}
              </p>
              <Link
                to="/signup"
                className="mt-4 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full bg-[var(--ink)] px-5 text-sm font-semibold text-white transition duration-150 ease-out hover:bg-black active:scale-[0.98]"
              >
                {t("marketing.pricing_calc.get_started")}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="mt-5 flex gap-2 rounded-lg bg-[var(--bg)] p-3 text-[11px] leading-relaxed text-[var(--ink-muted)]">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {t("marketing.pricing_calc.disclaimer")}{" "}
              <Link to="/pricing" className="underline hover:text-[var(--ink)]">
                {t("marketing.pricing_calc.disclaimer_link")}
              </Link>{" "}
              {t("marketing.pricing_calc.disclaimer_suffix")}
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

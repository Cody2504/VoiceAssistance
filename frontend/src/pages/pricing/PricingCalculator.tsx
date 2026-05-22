import { useMemo, useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, ArrowLeft, Info } from "lucide-react";

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

  return (
    <main className="mx-auto max-w-6xl px-6 pb-24 pt-12 md:pt-16">
      <Link
        to="/pricing"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--ink-soft)] transition hover:text-[var(--ink)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to pricing
      </Link>

      <header className="fade-rise mt-6 text-center">
        <h1 className="text-[40px] font-semibold tracking-[-0.02em] md:text-[56px]">
          Pricing calculator
        </h1>
        <p className="mx-auto mt-4 max-w-[52ch] text-sm text-[var(--ink-soft)] md:text-base">
          Estimate your monthly bill based on indexing volume, search activity, and generation
          calls. Edit any field — totals update live.
        </p>
      </header>

      <div className="mt-12 grid gap-8 md:grid-cols-[1.3fr_1fr]">
        {/* LEFT: inputs */}
        <div className="space-y-8">
          {/* Eclipse */}
          <section className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <FamilyHeader id="eclipse" />
            <p className="mt-1 text-xs text-[var(--ink-muted)]">Indexing, search, moment grounding</p>

            <div className="mt-4 divide-y divide-[var(--line)]">
              <NumberField
                label="Estimate monthly video upload"
                hint={`$${ITEMS.find(i => i.id === "index")?.developerRate}/min`}
                value={inputs.indexHours}
                onChange={(v) => setInputs((s) => ({ ...s, indexHours: v }))}
                min={0}
                step={1}
                suffix="hours"
              />
              <NumberField
                label="Search API — monthly queries"
                hint="$3 / 1K queries"
                value={inputs.searchQueries}
                onChange={(v) => setInputs((s) => ({ ...s, searchQueries: v }))}
                min={0}
                step={100}
                suffix="queries"
              />
              <NumberField
                label="Moment grounding — monthly calls"
                hint="$0.005 / call"
                value={inputs.groundCalls}
                onChange={(v) => setInputs((s) => ({ ...s, groundCalls: v }))}
                min={0}
                step={10}
                suffix="calls"
              />
            </div>
          </section>

          {/* Secretariat */}
          <section className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <FamilyHeader id="secretariat" />
            <p className="mt-1 text-xs text-[var(--ink-muted)]">Time-range Q&A, whole-video summary</p>

            <div className="mt-4 divide-y divide-[var(--line)]">
              <NumberField
                label="Time-range Q&A — monthly calls"
                hint="$0.02 / call"
                value={inputs.qaCalls}
                onChange={(v) => setInputs((s) => ({ ...s, qaCalls: v }))}
                min={0}
                step={10}
                suffix="calls"
              />
              <NumberField
                label="Whole-video summary — monthly calls"
                hint="$0.10 / call"
                value={inputs.summarizeCalls}
                onChange={(v) => setInputs((s) => ({ ...s, summarizeCalls: v }))}
                min={0}
                step={5}
                suffix="calls"
              />
            </div>
          </section>

          <section className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-[var(--ink)]">Projection horizon</div>
                <div className="mt-0.5 text-xs text-[var(--ink-muted)]">
                  Multiplies monthly cost by N months. Useful for budgeting demos and trials.
                </div>
              </div>
              <select
                value={inputs.months}
                onChange={(e) => setInputs((s) => ({ ...s, months: Number(e.target.value) }))}
                className="rounded-lg border border-[var(--line)] bg-white px-3 py-1.5 text-sm focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
              >
                {[1, 3, 6, 12].map((m) => (
                  <option key={m} value={m}>
                    {m} month{m > 1 ? "s" : ""}
                  </option>
                ))}
              </select>
            </div>
          </section>
        </div>

        {/* RIGHT: live cost summary, sticky */}
        <aside>
          <div className="sticky top-20 rounded-3xl border border-[var(--line)] bg-white p-6 md:p-7">
            <div className="text-lg font-semibold text-[var(--ink)]">Cost summary</div>
            <p className="mt-0.5 text-xs text-[var(--ink-muted)]">
              Developer (pay-as-you-go) — updates live.
            </p>

            {/* Eclipse subtotal */}
            <div className="mt-5">
              <FamilyHeader id="eclipse" />
              <div className="mt-1">
                {itemRows
                  .filter(({ item }) => item.family === "eclipse")
                  .map(({ item, cost }) => (
                    <CostRow key={item.id} label={item.label} value={formatUSD(cost)} />
                  ))}
                <CostRow label="Eclipse subtotal" value={formatUSD(cost.byFamily.eclipse)} accent />
              </div>
            </div>

            {/* Secretariat subtotal */}
            <div className="mt-7">
              <FamilyHeader id="secretariat" />
              <div className="mt-1">
                {itemRows
                  .filter(({ item }) => item.family === "secretariat")
                  .map(({ item, cost }) => (
                    <CostRow key={item.id} label={item.label} value={formatUSD(cost)} />
                  ))}
                <CostRow
                  label="Secretariat subtotal"
                  value={formatUSD(cost.byFamily.secretariat)}
                  accent
                />
              </div>
            </div>

            {/* Total */}
            <div className="mt-7 rounded-2xl bg-[var(--bg)] p-5">
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-[var(--ink-soft)]">Monthly total</span>
                <span className="text-2xl font-semibold tracking-tight">
                  {formatUSD(monthlyTotal)}
                </span>
              </div>
              {inputs.months > 1 && (
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-xs text-[var(--ink-muted)]">
                    Projected ({inputs.months} months)
                  </span>
                  <span className="text-sm font-medium text-[var(--ink)]">
                    {formatUSD(projectedTotal)}
                  </span>
                </div>
              )}
            </div>

            {/* CTA */}
            <div className="mt-6">
              <div className="text-sm font-semibold text-[var(--ink)]">Start for free</div>
              <p className="mt-1 text-xs text-[var(--ink-muted)]">
                Free plan covers 5 hours of indexing and 1,000 search queries each month — no
                credit card required.
              </p>
              <Link
                to="/signup"
                className="mt-4 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full bg-[var(--ink)] px-5 text-sm font-semibold text-white transition hover:bg-black"
              >
                Get started
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="mt-5 flex gap-2 rounded-lg bg-[var(--bg)] p-3 text-[11px] leading-relaxed text-[var(--ink-muted)]">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Rates apply to the Developer plan. Free includes monthly caps; Enterprise uses
              committed contracts. See the{" "}
              <Link to="/pricing" className="underline hover:text-[var(--ink)]">
                pricing page
              </Link>{" "}
              for details.
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

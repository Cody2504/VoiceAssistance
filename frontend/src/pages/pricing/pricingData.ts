/**
 * Pricing source of truth for tl-jockey.
 *
 * Two capability families:
 *   - Eclipse:     retrieval — indexing, search, moment grounding
 *   - Secretariat: generation — time-range Q&A, whole-video summary
 *
 * Developer (pay-as-you-go) rates = real per-unit pipeline cost × ~10× to cover
 * idle GPU, storage, egress, ops and margin. Raw cost basis (2026-06): the
 * self-hosted stack on a Vast.ai RTX 4090 (~$0.35/hr GPU) —
 *   - index:     ~$0.003/video-min (TransNetV2 + CLIP-L + InternVideo2 + Whisper
 *                + PANN on GPU, plus per-shot Qwen3-VL captions)  → $0.03 / min
 *   - search:    ~$0/query (pgvector, CPU-bound)                  → $1.00 / 1K
 *   - ground:    ~$0.0002/call (cached IV2 feats + SG-DETR head)  → $0.002 / call
 *   - qa:        ~$0.0005/call (Qwen3-VL-8B, ~3k tokens)          → $0.005 / call
 *   - summarize: ~$0.0012/call (Qwen3-VL-8B, ~10k tokens)         → $0.01 / call
 * Free-tier caps mirror the seeded billing plan (300/1000/100/200/50 per month).
 * Edit here and both /pricing and /pricing-calculator update.
 *
 * All user-visible string fields are i18n keys — resolve with t() at the
 * consuming component.
 */

export type FamilyId = "eclipse" | "secretariat";
export type TierId = "free" | "developer" | "enterprise";

export interface ModelFamily {
  id: FamilyId;
  name: string;          // brand name — NOT translated (Eclipse / Secretariat)
  taglineKey: string;    // i18n key
  gradientClass: string; // tailwind gradient utility
}

export interface LineItem {
  id: string;
  family: FamilyId;
  labelKey: string;      // i18n key
  unit: string;          // "minute", "1K queries", "call" — internal billing unit, not shown raw
  unitShort: string;     // for compact tables — internal, not shown raw
  // Free tier monthly cap. Numeric = units included, "—" = not available.
  freeMonthly: number | "—";
  // Developer pay-as-you-go rate, $ per unit.
  developerRate: number;
}

export interface Tier {
  id: TierId;
  name: string;          // brand name — NOT translated
  subtitleKey: string;   // i18n key
  cta: { labelKey: string; href: string };
  accentClass: string;   // tailwind gradient for the column accent
}

export interface ComparisonRow {
  labelKey: string;
  free: string;
  developer: string;
  enterprise: string;
}

export const FAMILIES: Record<FamilyId, ModelFamily> = {
  eclipse: {
    id: "eclipse",
    name: "Eclipse",
    taglineKey: "marketing.pricing.families.eclipse_tagline",
    gradientClass: "from-emerald-200/80 via-yellow-100/70 to-rose-200/80",
  },
  secretariat: {
    id: "secretariat",
    name: "Secretariat",
    taglineKey: "marketing.pricing.families.secretariat_tagline",
    gradientClass: "from-rose-200/80 via-amber-200/80 to-yellow-300/80",
  },
};

export const ITEMS: LineItem[] = [
  {
    id: "index",
    family: "eclipse",
    labelKey: "marketing.pricing.items.index_label",
    unit: "minute",
    unitShort: "/min",
    freeMonthly: 300,              // 5 hours
    developerRate: 0.03,
  },
  {
    id: "search",
    family: "eclipse",
    labelKey: "marketing.pricing.items.search_label",
    unit: "1K queries",
    unitShort: "/1K queries",
    freeMonthly: 1000,
    developerRate: 1,
  },
  {
    id: "ground",
    family: "eclipse",
    labelKey: "marketing.pricing.items.ground_label",
    unit: "call",
    unitShort: "/call",
    freeMonthly: 100,
    developerRate: 0.002,
  },
  {
    id: "qa",
    family: "secretariat",
    labelKey: "marketing.pricing.items.qa_label",
    unit: "call",
    unitShort: "/call",
    freeMonthly: 200,
    developerRate: 0.005,
  },
  {
    id: "summarize",
    family: "secretariat",
    labelKey: "marketing.pricing.items.summarize_label",
    unit: "call",
    unitShort: "/call",
    freeMonthly: 50,
    developerRate: 0.01,
  },
];

export const TIERS: Tier[] = [
  {
    id: "free",
    name: "Free",
    subtitleKey: "marketing.pricing.tiers.free_subtitle",
    cta: { labelKey: "marketing.pricing.tiers.free_cta", href: "/signup" },
    accentClass: "bg-white",
  },
  {
    id: "developer",
    name: "Developer",
    subtitleKey: "marketing.pricing.tiers.developer_subtitle",
    cta: { labelKey: "marketing.pricing.tiers.developer_cta", href: "/settings/billing" },
    accentClass: "bg-gradient-to-b from-rose-50 to-amber-50",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    subtitleKey: "marketing.pricing.tiers.enterprise_subtitle",
    cta: { labelKey: "marketing.pricing.tiers.enterprise_cta", href: "mailto:hello@jockey.local" },
    accentClass: "bg-gradient-to-b from-lime-50 to-yellow-100",
  },
];

export const COMPARISON: ComparisonRow[] = [
  { labelKey: "marketing.pricing.comparison.row_hours",      free: "marketing.pricing.comparison.free_hours",      developer: "marketing.pricing.comparison.dev_hours",  enterprise: "marketing.pricing.comparison.ent_hours" },
  { labelKey: "marketing.pricing.comparison.row_retention",  free: "marketing.pricing.comparison.free_retention",  developer: "marketing.pricing.comparison.dev_retention", enterprise: "marketing.pricing.comparison.ent_retention" },
  { labelKey: "marketing.pricing.comparison.row_concurrent", free: "marketing.pricing.comparison.free_concurrent", developer: "marketing.pricing.comparison.dev_concurrent", enterprise: "marketing.pricing.comparison.ent_concurrent" },
  { labelKey: "marketing.pricing.comparison.row_max_length", free: "marketing.pricing.comparison.free_max_length", developer: "marketing.pricing.comparison.dev_max_length", enterprise: "marketing.pricing.comparison.ent_max_length" },
  { labelKey: "marketing.pricing.comparison.row_volume",     free: "marketing.pricing.comparison.free_volume",     developer: "marketing.pricing.comparison.dev_volume", enterprise: "marketing.pricing.comparison.ent_volume" },
];

export interface FAQ {
  qKey: string;
  aKey: string;
}

export const FAQS: FAQ[] = [
  { qKey: "marketing.pricing.faqs.q1", aKey: "marketing.pricing.faqs.a1" },
  { qKey: "marketing.pricing.faqs.q2", aKey: "marketing.pricing.faqs.a2" },
  { qKey: "marketing.pricing.faqs.q3", aKey: "marketing.pricing.faqs.a3" },
  { qKey: "marketing.pricing.faqs.q4", aKey: "marketing.pricing.faqs.a4" },
  { qKey: "marketing.pricing.faqs.q5", aKey: "marketing.pricing.faqs.a5" },
  { qKey: "marketing.pricing.faqs.q6", aKey: "marketing.pricing.faqs.a6" },
];

/** Compute monthly bill for Developer (pay-as-you-go) given a usage map. */
export function computeDeveloperCost(
  usage: Record<string, number>,
): { byItem: Record<string, number>; total: number; byFamily: Record<FamilyId, number> } {
  const byItem: Record<string, number> = {};
  const byFamily: Record<FamilyId, number> = { eclipse: 0, secretariat: 0 };
  for (const item of ITEMS) {
    const qty = usage[item.id] ?? 0;
    const cost = qty * item.developerRate;
    byItem[item.id] = cost;
    byFamily[item.family] += cost;
  }
  const total = Object.values(byItem).reduce((a, b) => a + b, 0);
  return { byItem, total, byFamily };
}

export function formatUSD(n: number): string {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

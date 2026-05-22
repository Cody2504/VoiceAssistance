/**
 * Pricing source of truth for tl-jockey.
 *
 * Two model families (mirroring TwelveLabs' Marengo/Pegasus split):
 *   - Eclipse:     retrieval — indexing, search, moment grounding
 *   - Secretariat: generation — time-range Q&A, whole-video summary
 *
 * Numbers reflect actual compute costs (Colab T4 ~$0.30/hr) with margin.
 * Edit here and both /pricing and /pricing-calculator update.
 */

export type FamilyId = "eclipse" | "secretariat";
export type TierId = "free" | "developer" | "enterprise";

export interface ModelFamily {
  id: FamilyId;
  name: string;
  tagline: string;
  gradientClass: string;  // tailwind gradient utility
}

export interface LineItem {
  id: string;
  family: FamilyId;
  label: string;
  unit: string;             // "minute", "1K queries", "call"
  unitShort: string;        // for compact tables
  // Free tier monthly cap. Numeric = units included, "—" = not available.
  freeMonthly: number | "—";
  // Developer pay-as-you-go rate, $ per unit.
  developerRate: number;
}

export interface Tier {
  id: TierId;
  name: string;
  subtitle: string;
  cta: { label: string; href: string };
  accentClass: string;  // tailwind gradient for the column accent
}

export interface ComparisonRow {
  label: string;
  free: string;
  developer: string;
  enterprise: string;
}

export const FAMILIES: Record<FamilyId, ModelFamily> = {
  eclipse: {
    id: "eclipse",
    name: "Eclipse",
    tagline:
      "Our retrieval model — indexes video frames, speech, and ambient audio into a searchable temporal space, with moment-level grounding from a single text query.",
    gradientClass: "from-emerald-200/80 via-yellow-100/70 to-rose-200/80",
  },
  secretariat: {
    id: "secretariat",
    name: "Secretariat",
    tagline:
      "Our generation model — answers questions about a chosen time range and summarizes whole videos, reading frames and transcripts together to produce grounded text.",
    gradientClass: "from-rose-200/80 via-amber-200/80 to-yellow-300/80",
  },
};

export const ITEMS: LineItem[] = [
  {
    id: "index",
    family: "eclipse",
    label: "Video indexing",
    unit: "minute",
    unitShort: "/min",
    freeMonthly: 300,              // 5 hours
    developerRate: 0.04,
  },
  {
    id: "search",
    family: "eclipse",
    label: "Search API",
    unit: "1K queries",
    unitShort: "/1K queries",
    freeMonthly: 1000,
    developerRate: 3,
  },
  {
    id: "ground",
    family: "eclipse",
    label: "Moment grounding",
    unit: "call",
    unitShort: "/call",
    freeMonthly: 100,
    developerRate: 0.005,
  },
  {
    id: "qa",
    family: "secretariat",
    label: "Time-range Q&A",
    unit: "call",
    unitShort: "/call",
    freeMonthly: 200,
    developerRate: 0.02,
  },
  {
    id: "summarize",
    family: "secretariat",
    label: "Whole-video summary",
    unit: "call",
    unitShort: "/call",
    freeMonthly: 50,
    developerRate: 0.1,
  },
];

export const TIERS: Tier[] = [
  {
    id: "free",
    name: "Free",
    subtitle: "Up to 5 hours of indexing",
    cta: { label: "Get Started", href: "/signup" },
    accentClass: "bg-white",
  },
  {
    id: "developer",
    name: "Developer",
    subtitle: "Pay as you go",
    cta: { label: "Upgrade", href: "/signup" },
    accentClass: "bg-gradient-to-b from-rose-50 to-amber-50",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    subtitle: "Committed use contracts",
    cta: { label: "Talk to Sales", href: "mailto:hello@jockey.local" },
    accentClass: "bg-gradient-to-b from-lime-50 to-yellow-100",
  },
];

export const COMPARISON: ComparisonRow[] = [
  { label: "Video hours / month", free: "5 hours", developer: "Unlimited", enterprise: "Unlimited" },
  { label: "Index retention", free: "30 days since creation", developer: "Unlimited", enterprise: "Unlimited" },
  { label: "Concurrent indexing tasks", free: "2", developer: "10", enterprise: "Custom" },
  { label: "Max video length", free: "60 min", developer: "240 min", enterprise: "Unlimited" },
  { label: "Volume per index", free: "100 videos", developer: "10,000 videos", enterprise: "Custom" },
];

export interface FAQ {
  q: string;
  a: string;
}

export const FAQS: FAQ[] = [
  {
    q: "Do I need to register a credit card to use the Free plan?",
    a: "No. The Free plan is fully usable without a payment method. Once you exceed your monthly caps you'll be prompted to add billing to continue.",
  },
  {
    q: "What happens to my index if I switch from Free to Developer?",
    a: "Your indexes are preserved. The 30-day retention cap on Free is removed and your videos remain searchable indefinitely while you're on the paid plan.",
  },
  {
    q: "How is moment grounding billed?",
    a: "Each call to the Moment Grounding endpoint — text query → (start_sec, end_sec) — counts as one call. The Free plan includes 100 calls per month; beyond that the Developer rate is $0.005 per call.",
  },
  {
    q: "Can I fine-tune the models?",
    a: "Eclipse's grounding head can be fine-tuned on your own (query, video, span) data on Enterprise plans. Talk to sales for the fine-tuning workflow.",
  },
  {
    q: "How is video indexing duration measured?",
    a: "Indexing minutes are charged based on the total video duration submitted, not the wall-clock time taken to process. A 10-minute video always counts as 10 minutes regardless of GPU contention.",
  },
  {
    q: "What's the difference between Eclipse and Secretariat?",
    a: "Eclipse handles retrieval (finding videos and moments). Secretariat handles generation (answering questions and writing summaries). Most products use both: Eclipse to locate, Secretariat to describe.",
  },
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

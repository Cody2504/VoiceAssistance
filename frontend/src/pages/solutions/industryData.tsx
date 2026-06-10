import type { ComponentType } from "react";
import { Clapperboard, Megaphone, ShieldCheck, Car, type LucideIcon } from "lucide-react";

/**
 * Content for the four industry solution pages, mirroring the structure of
 * twelvelabs.io/solutions/* on the Jockey light skin:
 *   hero · numbered feature tiles · use cases · value pillars · pricing · CTA.
 * Value pillars and pricing tiers are shared across industries (see
 * SolutionPage); only the industry-specific copy lives here. Guest-facing.
 *
 * All user-visible string fields are i18n keys — resolve with t() at the
 * consuming component (SolutionPage.tsx).
 */

export interface UseCaseGroup {
  titleKey: string;
  itemsKey: string;
}

export interface Feature {
  n: string;
  titleKey: string;
  bodyKey: string;
  /** rounded image tile shown above the title */
  image: string;
  /** i18n key for frosted caption chip; empty string = no chip */
  captionKey: string;
}

export interface IndustryData {
  slug: string;
  icon: LucideIcon;
  eyebrowKey: string;
  heroTitleKey: string;
  heroSubKey: string;
  /** background media for the framed hero visual */
  media: { type: "video"; src: string; poster: string } | { type: "image"; src: string };
  /** pastel tint + ink colour used for accents / image-tile fallback */
  tone: string;
  ink: string;
  features: Feature[];
  useCasesHeadingKey: string;
  useCaseGroups: UseCaseGroup[];
  ctaTitleKey: string;
}

export const SOLUTIONS: Record<string, IndustryData> = {
  "media-and-entertainment": {
    slug: "media-and-entertainment",
    icon: Clapperboard,
    eyebrowKey: "marketing.solution_page.industries.media_eyebrow",
    heroTitleKey: "marketing.solution_page.industries.media_hero_title",
    heroSubKey: "marketing.solution_page.industries.media_hero_sub",
    media: { type: "image", src: "/twelvelabs/me-hero.png" },
    tone: "bg-[#fbdfff]",
    ink: "text-[#5e3b66]",
    features: [
      {
        n: "01",
        titleKey: "marketing.solution_page.industries.media_f1_title",
        bodyKey: "marketing.solution_page.industries.media_f1_body",
        image: "/twelvelabs/me-01-archive.png",
        captionKey: "",
      },
      {
        n: "02",
        titleKey: "marketing.solution_page.industries.media_f2_title",
        bodyKey: "marketing.solution_page.industries.media_f2_body",
        image: "/twelvelabs/me-02-production.png",
        captionKey: "",
      },
      {
        n: "03",
        titleKey: "marketing.solution_page.industries.media_f3_title",
        bodyKey: "marketing.solution_page.industries.media_f3_body",
        image: "/twelvelabs/me-03-repackage.png",
        captionKey: "",
      },
    ],
    useCasesHeadingKey: "marketing.solution_page.industries.media_usecases_heading",
    useCaseGroups: [
      {
        titleKey: "marketing.solution_page.industries.media_uc1_title",
        itemsKey: "marketing.solution_page.industries.media_uc1_items",
      },
      {
        titleKey: "marketing.solution_page.industries.media_uc2_title",
        itemsKey: "marketing.solution_page.industries.media_uc2_items",
      },
      {
        titleKey: "marketing.solution_page.industries.media_uc3_title",
        itemsKey: "marketing.solution_page.industries.media_uc3_items",
      },
    ],
    ctaTitleKey: "marketing.solution_page.industries.media_cta_title",
  },

  advertising: {
    slug: "advertising",
    icon: Megaphone,
    eyebrowKey: "marketing.solution_page.industries.ad_eyebrow",
    heroTitleKey: "marketing.solution_page.industries.ad_hero_title",
    heroSubKey: "marketing.solution_page.industries.ad_hero_sub",
    media: { type: "image", src: "/twelvelabs/ad-hero.png" },
    tone: "bg-[#fde3a2]",
    ink: "text-[#7d5d0c]",
    features: [
      {
        n: "01",
        titleKey: "marketing.solution_page.industries.ad_f1_title",
        bodyKey: "marketing.solution_page.industries.ad_f1_body",
        image: "/twelvelabs/ad-01-context.png",
        captionKey: "",
      },
      {
        n: "02",
        titleKey: "marketing.solution_page.industries.ad_f2_title",
        bodyKey: "marketing.solution_page.industries.ad_f2_body",
        image: "/twelvelabs/ad-02-safety.png",
        captionKey: "",
      },
      {
        n: "03",
        titleKey: "marketing.solution_page.industries.ad_f3_title",
        bodyKey: "marketing.solution_page.industries.ad_f3_body",
        image: "/twelvelabs/ad-03-creative.png",
        captionKey: "",
      },
    ],
    useCasesHeadingKey: "marketing.solution_page.industries.ad_usecases_heading",
    useCaseGroups: [
      {
        titleKey: "marketing.solution_page.industries.ad_uc1_title",
        itemsKey: "marketing.solution_page.industries.ad_uc1_items",
      },
      {
        titleKey: "marketing.solution_page.industries.ad_uc2_title",
        itemsKey: "marketing.solution_page.industries.ad_uc2_items",
      },
      {
        titleKey: "marketing.solution_page.industries.ad_uc3_title",
        itemsKey: "marketing.solution_page.industries.ad_uc3_items",
      },
    ],
    ctaTitleKey: "marketing.solution_page.industries.ad_cta_title",
  },

  "government-and-security": {
    slug: "government-and-security",
    icon: ShieldCheck,
    eyebrowKey: "marketing.solution_page.industries.gov_eyebrow",
    heroTitleKey: "marketing.solution_page.industries.gov_hero_title",
    heroSubKey: "marketing.solution_page.industries.gov_hero_sub",
    media: { type: "image", src: "/twelvelabs/gov-hero.png" },
    tone: "bg-[#c4eefe]",
    ink: "text-[#26586d]",
    features: [
      {
        n: "01",
        titleKey: "marketing.solution_page.industries.gov_f1_title",
        bodyKey: "marketing.solution_page.industries.gov_f1_body",
        image: "/twelvelabs/gov-01-fusion.png",
        captionKey: "",
      },
      {
        n: "02",
        titleKey: "marketing.solution_page.industries.gov_f2_title",
        bodyKey: "marketing.solution_page.industries.gov_f2_body",
        image: "/twelvelabs/gov-02-incident.png",
        captionKey: "",
      },
      {
        n: "03",
        titleKey: "marketing.solution_page.industries.gov_f3_title",
        bodyKey: "marketing.solution_page.industries.gov_f3_body",
        image: "/twelvelabs/gov-03-evidence.png",
        captionKey: "",
      },
    ],
    useCasesHeadingKey: "marketing.solution_page.industries.gov_usecases_heading",
    useCaseGroups: [
      {
        titleKey: "marketing.solution_page.industries.gov_uc1_title",
        itemsKey: "marketing.solution_page.industries.gov_uc1_items",
      },
      {
        titleKey: "marketing.solution_page.industries.gov_uc2_title",
        itemsKey: "marketing.solution_page.industries.gov_uc2_items",
      },
      {
        titleKey: "marketing.solution_page.industries.gov_uc3_title",
        itemsKey: "marketing.solution_page.industries.gov_uc3_items",
      },
    ],
    ctaTitleKey: "marketing.solution_page.industries.gov_cta_title",
  },

  automotive: {
    slug: "automotive",
    icon: Car,
    eyebrowKey: "marketing.solution_page.industries.auto_eyebrow",
    heroTitleKey: "marketing.solution_page.industries.auto_hero_title",
    heroSubKey: "marketing.solution_page.industries.auto_hero_sub",
    media: { type: "image", src: "/twelvelabs/auto-hero.png" },
    tone: "bg-[#d9f5dd]",
    ink: "text-[#2f6b3a]",
    features: [
      {
        n: "01",
        titleKey: "marketing.solution_page.industries.auto_f1_title",
        bodyKey: "marketing.solution_page.industries.auto_f1_body",
        image: "/twelvelabs/auto-01-find.png",
        captionKey: "",
      },
      {
        n: "02",
        titleKey: "marketing.solution_page.industries.auto_f2_title",
        bodyKey: "marketing.solution_page.industries.auto_f2_body",
        image: "/twelvelabs/auto-02-content.png",
        captionKey: "",
      },
      {
        n: "03",
        titleKey: "marketing.solution_page.industries.auto_f3_title",
        bodyKey: "marketing.solution_page.industries.auto_f3_body",
        image: "/twelvelabs/auto-03-intel.png",
        captionKey: "",
      },
    ],
    useCasesHeadingKey: "marketing.solution_page.industries.auto_usecases_heading",
    useCaseGroups: [
      {
        titleKey: "marketing.solution_page.industries.auto_uc1_title",
        itemsKey: "marketing.solution_page.industries.auto_uc1_items",
      },
      {
        titleKey: "marketing.solution_page.industries.auto_uc2_title",
        itemsKey: "marketing.solution_page.industries.auto_uc2_items",
      },
      {
        titleKey: "marketing.solution_page.industries.auto_uc3_title",
        itemsKey: "marketing.solution_page.industries.auto_uc3_items",
      },
    ],
    ctaTitleKey: "marketing.solution_page.industries.auto_cta_title",
  },
};

/* shared across all industry pages */

/* Inner glyphs for the value pillars — drawn to mirror the twelvelabs.io
 * "Our Value" icons. Stroked with currentColor so the renderer's box border
 * (light) and the glyph (dark) can differ. */
type GlyphProps = { className?: string };
const svgBase = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

function AccuracyGlyph({ className }: GlyphProps) {
  return (
    <svg {...svgBase} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
function ScaleGlyph({ className }: GlyphProps) {
  return (
    <svg {...svgBase} className={className}>
      <path d="M10 10 4 4M4 9V4h5" />
      <path d="M14 10l6-6M15 4h5v5" />
      <path d="M10 14l-6 6M4 15v5h5" />
      <path d="M14 14l6 6M20 15v5h-5" />
    </svg>
  );
}
function CustomizeGlyph({ className }: GlyphProps) {
  return (
    <svg {...svgBase} className={className}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <circle cx="6.5" cy="17.5" r="3.5" />
      <path d="M17.5 14v7M14 17.5h7" />
    </svg>
  );
}
function DeployGlyph({ className }: GlyphProps) {
  return (
    <svg {...svgBase} className={className}>
      <path d="M12 13v8" />
      <path d="m8 17 4 4 4-4" />
      <path d="M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25" />
    </svg>
  );
}

export const VALUE_PILLARS: { icon: ComponentType<GlyphProps>; titleKey: string; bodyKey: string }[] = [
  { icon: AccuracyGlyph, titleKey: "marketing.solution_page.pillars.accuracy_title", bodyKey: "marketing.solution_page.pillars.accuracy_body" },
  { icon: ScaleGlyph,    titleKey: "marketing.solution_page.pillars.scale_title",    bodyKey: "marketing.solution_page.pillars.scale_body" },
  { icon: CustomizeGlyph, titleKey: "marketing.solution_page.pillars.customize_title", bodyKey: "marketing.solution_page.pillars.customize_body" },
  { icon: DeployGlyph,   titleKey: "marketing.solution_page.pillars.deploy_title",   bodyKey: "marketing.solution_page.pillars.deploy_body" },
];

export interface PriceRow {
  labelKey: string;
  /** when present the row is "included": shown with a check + value */
  valueKey?: string;
}
export interface PricingTier {
  nameKey: string;
  descriptionKey: string;
  ctaKey: string;
  to: string;
  rows: PriceRow[];
}

export const PRICING_TIERS: PricingTier[] = [
  {
    nameKey: "marketing.solution_page.tiers.free_name",
    descriptionKey: "marketing.solution_page.tiers.free_desc",
    ctaKey: "marketing.solution_page.tiers.free_cta",
    to: "/signup",
    rows: [
      { labelKey: "marketing.solution_page.tiers.row_indexing", valueKey: "marketing.solution_page.tiers.val_10h" },
      { labelKey: "marketing.solution_page.tiers.row_environment", valueKey: "marketing.solution_page.tiers.val_shared" },
      { labelKey: "marketing.solution_page.tiers.row_org" },
      { labelKey: "marketing.solution_page.tiers.row_sso" },
      { labelKey: "marketing.solution_page.tiers.row_finetune" },
    ],
  },
  {
    nameKey: "marketing.solution_page.tiers.developer_name",
    descriptionKey: "marketing.solution_page.tiers.developer_desc",
    ctaKey: "marketing.solution_page.tiers.developer_cta",
    to: "/pricing",
    rows: [
      { labelKey: "marketing.solution_page.tiers.row_indexing", valueKey: "marketing.solution_page.tiers.val_10k" },
      { labelKey: "marketing.solution_page.tiers.row_environment", valueKey: "marketing.solution_page.tiers.val_shared" },
      { labelKey: "marketing.solution_page.tiers.row_org" },
      { labelKey: "marketing.solution_page.tiers.row_sso" },
      { labelKey: "marketing.solution_page.tiers.row_finetune" },
    ],
  },
  {
    nameKey: "marketing.solution_page.tiers.enterprise_name",
    descriptionKey: "marketing.solution_page.tiers.enterprise_desc",
    ctaKey: "marketing.solution_page.tiers.enterprise_cta",
    to: "/#cta",
    rows: [
      { labelKey: "marketing.solution_page.tiers.row_indexing", valueKey: "marketing.solution_page.tiers.val_unlimited" },
      { labelKey: "marketing.solution_page.tiers.row_environment", valueKey: "marketing.solution_page.tiers.val_dedicated" },
      { labelKey: "marketing.solution_page.tiers.row_org", valueKey: "marketing.solution_page.tiers.val_included" },
      { labelKey: "marketing.solution_page.tiers.row_sso", valueKey: "marketing.solution_page.tiers.val_included" },
      { labelKey: "marketing.solution_page.tiers.row_finetune", valueKey: "marketing.solution_page.tiers.val_included" },
    ],
  },
];

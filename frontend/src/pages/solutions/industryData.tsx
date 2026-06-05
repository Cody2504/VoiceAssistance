import type { ComponentType } from "react";
import { Clapperboard, Megaphone, ShieldCheck, Car, type LucideIcon } from "lucide-react";

/**
 * Content for the four industry solution pages, mirroring the structure of
 * twelvelabs.io/solutions/* on the Jockey light skin:
 *   hero · numbered feature tiles · use cases · value pillars · pricing · CTA.
 * Value pillars and pricing tiers are shared across industries (see
 * SolutionPage); only the industry-specific copy lives here. Guest-facing.
 */

export interface UseCaseGroup {
  title: string;
  items: string[];
}

export interface Feature {
  n: string;
  title: string;
  body: string;
  /** rounded image tile shown above the title */
  image: string;
  /** frosted caption chip overlaid on the image */
  caption: string;
}

export interface IndustryData {
  slug: string;
  icon: LucideIcon;
  eyebrow: string;
  heroTitle: string;
  heroSub: string;
  /** background media for the framed hero visual */
  media: { type: "video"; src: string; poster: string } | { type: "image"; src: string };
  /** pastel tint + ink colour used for accents / image-tile fallback */
  tone: string;
  ink: string;
  features: Feature[];
  useCasesHeading: string;
  useCaseGroups: UseCaseGroup[];
  ctaTitle: string;
}

export const SOLUTIONS: Record<string, IndustryData> = {
  "media-and-entertainment": {
    slug: "media-and-entertainment",
    icon: Clapperboard,
    eyebrow: "Media & Entertainment",
    heroTitle: "Less work.\nMore flow.",
    heroSub:
      "AI that indexes every scene, dialogue line and visual detail – so you can find, isolate and build stories in seconds.",
    media: { type: "image", src: "/twelvelabs/me-hero.png" },
    tone: "bg-[#fbdfff]",
    ink: "text-[#5e3b66]",
    features: [
      {
        n: "01",
        title: "Archive Segmentation",
        body: "Turn decades of footage into scene-level, searchable intelligence – pinpointing exact moments across your archive.",
        image: "/twelvelabs/me-01-archive.png",
        caption: "", // caption is baked into the source image

      },
      {
        n: "02",
        title: "Production Acceleration",
        body: "From raw footage to rough cut, automatically organize clips into searchable bins, highlights and chapters.",
        image: "/twelvelabs/me-02-production.png",
        caption: "", // caption is baked into the source image

      },
      {
        n: "03",
        title: "Content Repackaging",
        body: "Turn a single source video into trailers, social clips and regional edits, using natural language search.",
        image: "/twelvelabs/me-03-repackage.png",
        caption: "", // caption is baked into the source image

      },
    ],
    useCasesHeading: "AI for media that makes the cut.",
    useCaseGroups: [
      {
        title: "Shorter production workflows",
        items: ["Instant content summarization", "Automated ‘dailies’ editing", "Instant highlight reels and trailers"],
      },
      {
        title: "Tag-free content management",
        items: ["Duplicate content detection", "Metadata generation", "Deep semantic search", "Archive and rights management"],
      },
      {
        title: "More personalized user experiences",
        items: ["Contextualized content understanding", "Customer content recommendations", "Enhanced customer discovery", "Ad matching"],
      },
    ],
    ctaTitle: "Give your stories a new beginning.",
  },

  advertising: {
    slug: "advertising",
    icon: Megaphone,
    eyebrow: "Advertising",
    heroTitle: "Understands context.\nDrives performance.",
    heroSub:
      "AI that analyzes video context and message – then connects it to the audiences most likely to engage and convert.",
    media: { type: "image", src: "/twelvelabs/ad-hero.png" },
    tone: "bg-[#fde3a2]",
    ink: "text-[#7d5d0c]",
    features: [
      {
        n: "01",
        title: "Contextual placement",
        body: "Match ads to content moments by theme, tone and emotion. Now every placement feels intentional.",
        image: "/twelvelabs/ad-01-context.png",
        caption: "", // caption is baked into the source image
      },
      {
        n: "02",
        title: "Brand safety",
        body: "Automatically detect and filter unsafe or conflicting content in real time – protecting your brand at speed and scale.",
        image: "/twelvelabs/ad-02-safety.png",
        caption: "", // caption is baked into the source image
      },
      {
        n: "03",
        title: "Creative intelligence",
        body: "Pinpoint the creative messaging and moments that drive audience response – then double down on what’s working.",
        image: "/twelvelabs/ad-03-creative.png",
        caption: "", // caption is baked into the source image
      },
    ],
    useCasesHeading: "This is advertising now.",
    useCaseGroups: [
      { title: "Bolster production efficiencies", items: ["Instant rough cut creation", "Lightning-fast video workflows", "Quick ideation and creative development"] },
      { title: "Advanced ad management", items: ["Semantic search for deep discovery", "Tag-free inventory management", "Swift and easy metadata generation", "Analyze content safety & suitability"] },
      { title: "More personalized user experiences", items: ["Hyper contextual content alignment", "Elevated organic brand presence", "AI-driven search and discovery"] },
    ],
    ctaTitle: "See your video in a whole new way.",
  },

  "government-and-security": {
    slug: "government-and-security",
    icon: ShieldCheck,
    eyebrow: "Government & Security",
    heroTitle: "Turn fragmented footage\ninto unified intelligence.",
    heroSub:
      "Securely connect signals and activity across vast networks of cameras and sources – to build a complete operational picture.",
    media: { type: "image", src: "/twelvelabs/gov-hero.png" },
    tone: "bg-[#c4eefe]",
    ink: "text-[#26586d]",
    features: [
      {
        n: "01",
        title: "Cross-Source Fusion",
        body: "Unify CCTV, drone and satellite video into a single searchable intelligence system.",
        image: "/twelvelabs/gov-01-fusion.png",
        caption: "", // caption is baked into the source image
      },
      {
        n: "02",
        title: "Incident response",
        body: "Analyze critical footage and generate actionable summaries in minutes.",
        image: "/twelvelabs/gov-02-incident.png",
        caption: "", // caption is baked into the source image
      },
      {
        n: "03",
        title: "Evidence discovery",
        body: "Identify recurring patterns, linked events and anomalies across vast evidence archives.",
        image: "/twelvelabs/gov-03-evidence.png",
        caption: "", // caption is baked into the source image
      },
    ],
    useCasesHeading: "Security has never been so simple.",
    useCaseGroups: [
      { title: "Search across millions of video hours", items: ["Tag-free semantic exploration", "Natural language prompts and tailored search", "Time-stamped and confidence-scored results"] },
      { title: "Make sense of vast video footage", items: ["Automated surveillance footage analysis", "Metadata generation", "Pattern and anomaly detection"] },
      { title: "Understand your security posture", items: ["Detailed AI-driven reports", "Contextualized content analysis", "Automated incident documentation"] },
    ],
    ctaTitle: "Your video has more to show you.",
  },

  automotive: {
    slug: "automotive",
    icon: Car,
    eyebrow: "Automotive",
    heroTitle: "Video AI for automotive\nintelligence.",
    heroSub:
      "From driver hazards to pedestrian intent – Jockey understands events on video like a human does, with the potential to transform safety and efficiency.",
    media: { type: "image", src: "/twelvelabs/auto-hero.png" },
    tone: "bg-[#d9f5dd]",
    ink: "text-[#2f6b3a]",
    features: [
      {
        n: "01",
        title: "Find anything and everything in your archive.",
        body: "Any scene, any sound, any object, any moment - ‘search’ has a whole new meaning.",
        image: "/twelvelabs/auto-01-find.png",
        caption: "",
      },
      {
        n: "02",
        title: "Turn vast video data into meaningful content.",
        body: "Draw out the highlights from your archives or make instant reels from millions of clips.",
        image: "/twelvelabs/auto-02-content.png",
        caption: "",
      },
      {
        n: "03",
        title: "Turn vast video data into actionable intelligence.",
        body: "Detailed AI-driven documentation and contextual analysis can help you understand what happened.",
        image: "/twelvelabs/auto-03-intel.png",
        caption: "",
      },
    ],
    useCasesHeading: "The future of automotive is automation.",
    useCaseGroups: [
      { title: "Search millions of video hours", items: ["Tag-free exploration in natural language", "Find any scene, object, or moment", "Time-stamped incident results"] },
      { title: "Make sense of video footage", items: ["Detailed AI-driven analysis", "Pattern and anomaly detection", "Metadata generation", "Archive and data management"] },
      { title: "Understand your data and systems", items: ["Contextualized content analysis", "Confidence-scored reports", "Detailed incident documentation", "Insights for improving safety and efficiency"] },
    ],
    ctaTitle: "See your video in a whole new way.",
  },
};

/* shared across all industry pages */

export const VALUE_HEADING = "State-of-the-art, straight out of the box.";
export const VALUE_SUB =
  "Use on any cloud, fine-tune with your own data, and deploy your custom model. We give you the keys to state-of-the-art AI that adapts to your specific needs.";

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

export const VALUE_PILLARS: { icon: ComponentType<GlyphProps>; title: string; body: string }[] = [
  { icon: AccuracyGlyph, title: "World-class accuracy.", body: "Our video-native AI beats benchmarks from cloud majors and open-source models." },
  { icon: ScaleGlyph, title: "At a monumental scale.", body: "Our powerful infrastructure handles the largest video libraries – even petabytes of data." },
  { icon: CustomizeGlyph, title: "With total customization.", body: "Our models can be easily trained on your data to become experts in your domain." },
  { icon: DeployGlyph, title: "And deployable anywhere.", body: "On cloud, private cloud, or on-premise – deploy safely and easily, wherever you need us." },
];

export const PRICING_TITLE = "Play for free. Pay as you go.";
export const PRICING_SUB =
  "Our tiered pricing lets you play and build, then launch and grow. Start with one of our foundational models and pay only for what you use.";

export interface PriceRow {
  label: string;
  /** when present the row is "included": shown with a check + value */
  value?: string;
}
export interface PricingTier {
  name: string;
  description: string;
  cta: string;
  to: string;
  rows: PriceRow[];
}

export const PRICING_TIERS: PricingTier[] = [
  {
    name: "Free",
    description: "For testing and building",
    cta: "Get started",
    to: "/signup",
    rows: [
      { label: "Indexing limit", value: "<10 hours" },
      { label: "Environment", value: "Shared" },
      { label: "Org account" },
      { label: "SSO / SAML" },
      { label: "Finetune" },
    ],
  },
  {
    name: "Developer",
    description: "For launching and growing",
    cta: "Upgrade",
    to: "/pricing",
    rows: [
      { label: "Indexing limit", value: "<10k hours" },
      { label: "Environment", value: "Shared" },
      { label: "Org account" },
      { label: "SSO / SAML" },
      { label: "Finetune" },
    ],
  },
  {
    name: "Enterprise",
    description: "For scaling and services",
    cta: "Learn more",
    to: "/#cta",
    rows: [
      { label: "Indexing limit", value: "Unlimited" },
      { label: "Environment", value: "Dedicated" },
      { label: "Org account", value: "Included" },
      { label: "SSO / SAML", value: "Included" },
      { label: "Finetune", value: "Included" },
    ],
  },
];

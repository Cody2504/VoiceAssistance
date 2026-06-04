import { Clapperboard, Megaphone, ShieldCheck, Car, type LucideIcon } from "lucide-react";

/**
 * Content for the four industry solution pages, mirroring the structure of
 * twelvelabs.io/solutions/* on the Jockey light skin. Value pillars, the code
 * sample and pricing tiers are shared across industries (see SolutionPage),
 * so only the industry-specific copy lives here.
 */

export interface UseCaseGroup {
  title: string;
  items: string[];
}

export interface IndustryData {
  slug: string;
  icon: LucideIcon;
  eyebrow: string;
  heroTitle: string;
  heroSub: string;
  /** background media for the framed hero visual */
  media: { type: "video"; src: string; poster: string } | { type: "image"; src: string };
  /** pastel tint + ink colour used for accents on this page */
  tone: string;
  ink: string;
  features: { n: string; title: string; body: string }[];
  useCasesHeading: string;
  useCaseGroups: UseCaseGroup[];
  ctaTitle: string;
}

export const SOLUTIONS: Record<string, IndustryData> = {
  "media-and-entertainment": {
    slug: "media-and-entertainment",
    icon: Clapperboard,
    eyebrow: "Media & Entertainment",
    heroTitle: "Less work. More flow.",
    heroSub:
      "AI that indexes every scene, dialogue line and visual detail, so you can find, isolate and build stories in seconds.",
    media: { type: "video", src: "/twelvelabs/search-bg.mp4", poster: "/twelvelabs/search-bg.jpg" },
    tone: "bg-[#fbdfff]",
    ink: "text-[#5e3b66]",
    features: [
      { n: "01", title: "Archive segmentation", body: "Turn decades of footage into scene-level, searchable intelligence, pinpointing exact moments across your archive." },
      { n: "02", title: "Production acceleration", body: "From raw footage to rough cut, automatically organize clips into searchable bins, highlights and chapters." },
      { n: "03", title: "Content repackaging", body: "Turn a single source video into trailers, social clips and regional edits using natural language search." },
    ],
    useCasesHeading: "AI for media that makes the cut.",
    useCaseGroups: [
      { title: "Shorter production workflows", items: ["Instant rough-cut creation", "Searchable bins and chapters", "Faster ideation to delivery"] },
      { title: "Tag-free content management", items: ["Semantic search across the archive", "Auto-generated metadata", "No manual tagging", "Find any moment by description"] },
      { title: "Personalized experiences", items: ["Contextual recommendations", "Regional and platform edits", "AI-driven discovery", "Highlight reels on demand"] },
    ],
    ctaTitle: "Give your stories a new beginning.",
  },

  advertising: {
    slug: "advertising",
    icon: Megaphone,
    eyebrow: "Advertising",
    heroTitle: "Understands context. Drives performance.",
    heroSub:
      "AI that analyzes video context and message, then connects it to the audiences most likely to engage and convert.",
    media: { type: "image", src: "/twelvelabs/analyze-bg.png" },
    tone: "bg-[#fde3a2]",
    ink: "text-[#7d5d0c]",
    features: [
      { n: "01", title: "Contextual placement", body: "Match ads to content moments by theme, tone and emotion. Now every placement feels intentional." },
      { n: "02", title: "Brand safety", body: "Automatically detect and filter unsafe or conflicting content in real time, protecting your brand at speed and scale." },
      { n: "03", title: "Creative intelligence", body: "Pinpoint the creative messaging and moments that drive audience response, then double down on what is working." },
    ],
    useCasesHeading: "This is advertising now.",
    useCaseGroups: [
      { title: "Production efficiencies", items: ["Instant rough-cut creation", "Lightning-fast workflows", "Quick ideation"] },
      { title: "Advanced ad management", items: ["Semantic inventory search", "Tag-free inventory", "Metadata generation", "Content safety analysis"] },
      { title: "Personalized experiences", items: ["Contextual alignment", "Consistent brand presence", "AI-driven discovery"] },
    ],
    ctaTitle: "See your video in a whole new way.",
  },

  "government-and-security": {
    slug: "government-and-security",
    icon: ShieldCheck,
    eyebrow: "Government & Security",
    heroTitle: "Turn fragmented footage into unified intelligence.",
    heroSub:
      "Securely connect signals and activity across vast networks of cameras and sources, to build a complete operational picture.",
    media: { type: "image", src: "/twelvelabs/embed-bg.png" },
    tone: "bg-[#c4eefe]",
    ink: "text-[#26586d]",
    features: [
      { n: "01", title: "Cross-source fusion", body: "Unify CCTV, drone and satellite video into a single searchable intelligence system." },
      { n: "02", title: "Incident response", body: "Analyze critical footage and generate actionable summaries in minutes." },
      { n: "03", title: "Evidence discovery", body: "Identify recurring patterns, linked events and anomalies across vast evidence archives." },
    ],
    useCasesHeading: "Security has never been so simple.",
    useCaseGroups: [
      { title: "Search millions of hours", items: ["Tag-free semantic exploration", "Natural-language prompts", "Time-stamped, confidence-scored results"] },
      { title: "Make sense of footage", items: ["Automated analysis", "Metadata generation", "Pattern and anomaly detection"] },
      { title: "Understand your posture", items: ["AI-driven reports", "Contextualized analysis", "Automated documentation"] },
    ],
    ctaTitle: "Your video has more to show you.",
  },

  automotive: {
    slug: "automotive",
    icon: Car,
    eyebrow: "Automotive",
    heroTitle: "Video AI for automotive intelligence.",
    heroSub:
      "From driver hazards to pedestrian intent, Jockey understands events on video like a human does, with the potential to transform safety and efficiency.",
    media: { type: "image", src: "/twelvelabs/search-bg.jpg" },
    tone: "bg-[#d9f5dd]",
    ink: "text-[#2f6b3a]",
    features: [
      { n: "01", title: "Find anything in your archive", body: "Any scene, any sound, any object, any moment. Search has a whole new meaning." },
      { n: "02", title: "Turn data into content", body: "Draw out the highlights from your archives or make instant reels from millions of clips." },
      { n: "03", title: "Turn data into intelligence", body: "Detailed AI-driven documentation and contextual analysis help you understand what happened." },
    ],
    useCasesHeading: "The future of automotive is automation.",
    useCaseGroups: [
      { title: "Search millions of hours", items: ["Tag-free exploration in natural language", "Find any scene, object or moment", "Time-stamped incident results"] },
      { title: "Make sense of footage", items: ["Detailed AI-driven analysis", "Pattern and anomaly detection", "Metadata generation", "Archive and data management"] },
      { title: "Understand your systems", items: ["Contextualized content analysis", "Confidence-scored reports", "Detailed incident documentation", "Insights to improve safety"] },
    ],
    ctaTitle: "See your video in a whole new way.",
  },
};

/* shared across all industry pages */

export const VALUE_PILLARS = [
  { title: "World-class accuracy.", body: "Benchmark-beating retrieval and reasoning, straight out of the box." },
  { title: "At a monumental scale.", body: "Built to ingest and index petabytes of multimodal data." },
  { title: "With total customization.", body: "Fine-tune on your own data and adapt to your domain." },
  { title: "And deployable anywhere.", body: "Cloud, private cloud or fully on-premise." },
];

export const PRICING_TIERS = [
  { name: "Free", purpose: "For testing and building", indexing: "Up to 10 hours", cta: "Get started", to: "/signup", highlight: false },
  { name: "Developer", purpose: "For launching and growing", indexing: "Up to 10k hours", cta: "Upgrade", to: "/pricing", highlight: true },
  { name: "Enterprise", purpose: "For scaling and services", indexing: "Unlimited", cta: "Talk to sales", to: "/#cta", highlight: false },
];

export const SOLUTION_CODE = `from jockey import Jockey

client = Jockey("<YOUR_API_KEY>")

# Index a video, then search it in natural language
index = client.index.create(name="archive")
client.task.create(index_id=index.id, file="footage.mp4")

hits = client.search.query(index.id, "the moment it happened")
for hit in hits:
    print(hit.start, hit.end, hit.score)`;

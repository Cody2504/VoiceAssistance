import { useTranslation } from "react-i18next";
import { Hero } from "./sections/Hero";
import { Capabilities } from "./sections/Capabilities";
import { CapabilityDetail } from "./sections/CapabilityDetail";
import { SampleApps, type SampleAppCard } from "./sections/SampleApps";
import { Pricing } from "./sections/Pricing";
import { Models } from "./sections/Models";
import { Tutorials } from "./sections/Tutorials";
import { CallToAction } from "./sections/CallToAction";
import { Footer } from "./sections/Footer";
import { SearchIcon, AnalyzeIcon, EmbedIcon } from "@/components/brand/FeatureIcon";

const SEARCH_CARDS: SampleAppCard[] = [
  {
    titleKey: "landing.sample_apps.search_card1_title",
    bodyKey: "landing.sample_apps.search_card1_body",
    language: "Python",
    href: "#",
  },
  {
    titleKey: "landing.sample_apps.search_card2_title",
    bodyKey: "landing.sample_apps.search_card2_body",
    language: "Python",
    href: "#",
  },
  {
    titleKey: "landing.sample_apps.search_card3_title",
    bodyKey: "landing.sample_apps.search_card3_body",
    language: "Python",
    href: "#",
  },
];

const ANALYZE_CARDS: SampleAppCard[] = [
  {
    titleKey: "landing.sample_apps.analyze_card1_title",
    bodyKey: "landing.sample_apps.analyze_card1_body",
    language: "Node",
    href: "#",
  },
  {
    titleKey: "landing.sample_apps.analyze_card2_title",
    bodyKey: "landing.sample_apps.analyze_card2_body",
    language: "Node",
    href: "#",
  },
  {
    titleKey: "landing.sample_apps.analyze_card3_title",
    bodyKey: "landing.sample_apps.analyze_card3_body",
    language: "Python",
    href: "#",
  },
];

const EMBED_CARDS: SampleAppCard[] = [
  {
    titleKey: "landing.sample_apps.segment_card1_title",
    bodyKey: "landing.sample_apps.segment_card1_body",
    language: "Node",
    href: "#",
  },
  {
    titleKey: "landing.sample_apps.segment_card2_title",
    bodyKey: "landing.sample_apps.segment_card2_body",
    language: "Python",
    href: "#",
  },
  {
    titleKey: "landing.sample_apps.segment_card3_title",
    bodyKey: "landing.sample_apps.segment_card3_body",
    language: "Python",
    href: "#",
  },
];

export default function Landing() {
  const { t } = useTranslation();
  return (
    <>
      <Hero />
      <Capabilities />

      <CapabilityDetail
        id="search"
        eyebrow={t("landing.capability_detail.search_eyebrow")}
        eyebrowIcon={<SearchIcon size={22} />}
        title={t("landing.capability_detail.search_title")}
        body={t("landing.capability_detail.search_body")}
        backgroundVideo="/twelvelabs/search-bg.mp4"
        videoPoster="/twelvelabs/search-bg.jpg"
        contentTopClass="pt-6 md:pt-10"
        ctaTo="/playground/search"
        toneClass="text-[var(--color-obsidian)]"
      />

      <SampleApps
        headingKey="landing.sample_apps.search_heading"
        subtitleKey="landing.sample_apps.search_subtitle"
        cards={SEARCH_CARDS}
        panelClass="bg-[#fbdfff]"
        strokeClass="border-[#7b5880] text-[#7b5880]"
      />

      <CapabilityDetail
        id="analyze"
        eyebrow={t("landing.capability_detail.analyze_eyebrow")}
        eyebrowIcon={<AnalyzeIcon size={22} />}
        title={t("landing.capability_detail.analyze_title")}
        body={t("landing.capability_detail.analyze_body")}
        backgroundImage="/twelvelabs/analyze-bg.png"
        ctaTo="/playground/analyze"
        toneClass="text-[var(--color-obsidian)]"
      />

      <SampleApps
        headingKey="landing.sample_apps.analyze_heading"
        subtitleKey="landing.sample_apps.analyze_subtitle"
        cards={ANALYZE_CARDS}
        panelClass="bg-[#fde3a2]"
        strokeClass="border-[#7d5d0c] text-[#7d5d0c]"
      />

      <CapabilityDetail
        id="segment"
        eyebrow={t("landing.capability_detail.segment_eyebrow")}
        eyebrowIcon={<EmbedIcon size={22} />}
        title={t("landing.capability_detail.segment_title")}
        body={t("landing.capability_detail.segment_body")}
        backgroundImage="/twelvelabs/embed-bg.png"
        ctaTo="/playground/segment"
        toneClass="text-[var(--color-obsidian)]"
      />

      <SampleApps
        headingKey="landing.sample_apps.segment_heading"
        subtitleKey="landing.sample_apps.segment_subtitle"
        cards={EMBED_CARDS}
        panelClass="bg-[#c4eefe]"
        strokeClass="border-[#26586d] text-[#26586d]"
      />

      <Pricing />
      <Models />
      <Tutorials />
      <CallToAction />
      <Footer />
    </>
  );
}

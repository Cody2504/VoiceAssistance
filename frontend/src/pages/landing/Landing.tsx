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
    title: "Olympic Video Classification Application",
    body: "A powerful tool designed to categorize various Olympic sports using video clips.",
    language: "Python",
    href: "#",
  },
  {
    title: "Shade Finder App: Pinpoint Specific Colors in Videos",
    body: "Whether you're looking for the perfect berry-toned lipstick or just curious about spotting specific colors in your videos, this guide will help you leverage cutting-edge AI to do so effortlessly.",
    language: "Python",
    href: "#",
  },
  {
    title: "Video Highlight Generator",
    body: "The YouTube Chapter Highlight Generator is a tool developed to automatically generate chapter timestamps for YouTube videos.",
    language: "Python",
    href: "#",
  },
];

const ANALYZE_CARDS: SampleAppCard[] = [
  {
    title: "Generate social media posts for your videos",
    body: "This application simplifies the cross-platform video promotion workflow by generating unique posts for each social media platform.",
    language: "Node",
    href: "#",
  },
  {
    title: "Video Highlight Generator",
    body: "This application automatically analyzes video content to create chapters and highlights, streamlining the video production workflow for content creators.",
    language: "Node",
    href: "#",
  },
  {
    title: "Interview Analyzer",
    body: "This application evaluates job interview performances using the ability of the Pegasus video understanding engine to generate text based on video content.",
    language: "Python",
    href: "#",
  },
];

const EMBED_CARDS: SampleAppCard[] = [
  {
    title: "Contextual and Personalized Ads",
    body: "A tool for analyzing source footage, summarizing content, and recommending ads based on the footage's context and emotional tone.",
    language: "Node",
    href: "#",
  },
  {
    title: "Recommendations using Multimodal Embeddings",
    body: "Start exploring videos and discovering similar content powered by tl-jockey Multimodal Embeddings.",
    language: "Python",
    href: "#",
  },
  {
    title: "Semantic Domain Classifier",
    body: "Build your own classifier using natural language: define classes in plain English and run instantly on any new video.",
    language: "Python",
    href: "#",
  },
];

export default function Landing() {
  return (
    <>
      <Hero />
      <Capabilities />

      <CapabilityDetail
        eyebrow="Search"
        eyebrowIcon={<SearchIcon size={22} />}
        title="Find any scene in natural language."
        body="Fast, precise, context-aware results that truly understand what you're looking for. Search across speech, text, audio and visuals to explore your video in every dimension."
        backgroundVideo="/twelvelabs/search-bg.mp4"
        videoPoster="/twelvelabs/search-bg.jpg"
        contentTopClass="pt-6 md:pt-10"
        ctaTo="/playground/search"
        toneClass="text-[var(--color-obsidian)]"
      />

      <SampleApps
        heading="What do you want to find?"
        subtitle="Try 'search' with a Sample App"
        cards={SEARCH_CARDS}
        panelClass="bg-[#fbdfff]"
        strokeClass="border-[#7b5880] text-[#7b5880]"
      />

      <CapabilityDetail
        eyebrow="Analyze"
        eyebrowIcon={<AnalyzeIcon size={22} />}
        title="Summarize, analyze and describe."
        body="Create instant text formats like Q&As, hashtags, and summaries. Generate reports or get domain-specific analysis to answer your deepest questions."
        backgroundImage="/twelvelabs/analyze-bg.png"
        ctaTo="/playground/analyze"
        toneClass="text-[var(--color-obsidian)]"
      />

      <SampleApps
        heading="What do you want to describe?"
        subtitle="Try 'analyze' with a Sample App"
        cards={ANALYZE_CARDS}
        panelClass="bg-[#fde3a2]"
        strokeClass="border-[#7d5d0c] text-[#7d5d0c]"
      />

      <CapabilityDetail
        eyebrow="Segment"
        eyebrowIcon={<EmbedIcon size={22} />}
        title="Turn video into labeled chapters."
        body="Build features like semantic search and domain classification with embeddings that capture nuance — and make the most of all your data."
        backgroundImage="/twelvelabs/embed-bg.png"
        ctaTo="/playground/segment"
        toneClass="text-[var(--color-obsidian)]"
      />

      <SampleApps
        heading="What do you want to build?"
        subtitle="Try 'segment' with a Sample App"
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

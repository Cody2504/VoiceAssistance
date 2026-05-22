import { useTranslation } from "react-i18next";

import { FeatureCard } from "@/components/landing/FeatureCard";

function SearchIllustration() {
  return (
    <div className="flex w-40 flex-col gap-1.5">
      <div className="flex items-center gap-2 rounded-md border border-[var(--line)] bg-white px-2 py-1.5 text-[10px] text-[var(--ink-muted)]">
        <span className="rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[8px] font-bold text-white">Q</span>
        <span>"the goalkeeper save"</span>
      </div>
      <div className="h-3 rounded bg-[#f3f0ea] relative overflow-hidden">
        <span className="absolute top-0 bottom-0" style={{ left: "20%", width: "12%", background: "linear-gradient(90deg, #ff8caa, #7a4dff)", opacity: 0.75 }} />
        <span className="absolute top-0 bottom-0" style={{ left: "70%", width: "16%", background: "linear-gradient(90deg, #ff8caa, #7a4dff)", opacity: 0.75 }} />
      </div>
    </div>
  );
}

function SummarizeIllustration() {
  return (
    <div className="flex w-40 flex-col gap-1.5">
      {[100, 88, 94, 70].map((w, i) => (
        <div
          key={i}
          className="h-2 rounded"
          style={{
            width: `${w}%`,
            background: i === 0 ? "linear-gradient(90deg, #7a4dff, #ff8caa)" : "#e5e1d6",
          }}
        />
      ))}
    </div>
  );
}

function FindIllustration() {
  return (
    <div className="grid w-40 grid-cols-3 gap-1.5">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="aspect-[16/10] rounded"
          style={{
            background: i === 4
              ? "linear-gradient(135deg, #2a1a44, #1c1024)"
              : "linear-gradient(135deg, #f0eada, #e0d4f0)",
            boxShadow: i === 4 ? "0 0 0 2px var(--accent)" : "none",
          }}
        />
      ))}
    </div>
  );
}

export function Features() {
  const { t } = useTranslation();
  return (
    <section id="features" className="bg-white">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="mx-auto max-w-2xl text-center text-3xl font-semibold tracking-tight md:text-4xl">
          {t("landing.features.title")}
        </h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          <FeatureCard
            title={t("landing.features.search.title")}
            body={t("landing.features.search.body")}
            illustration={<SearchIllustration />}
          />
          <FeatureCard
            title={t("landing.features.summarize.title")}
            body={t("landing.features.summarize.body")}
            illustration={<SummarizeIllustration />}
          />
          <FeatureCard
            title={t("landing.features.find.title")}
            body={t("landing.features.find.body")}
            illustration={<FindIllustration />}
          />
        </div>
      </div>
    </section>
  );
}

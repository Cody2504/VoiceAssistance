import { useTranslation } from "react-i18next";

import { StepCard } from "@/components/landing/StepCard";

function UploadIllu() {
  return (
    <div className="grid w-32 grid-cols-2 gap-1">
      <div className="aspect-square rounded" style={{ background: "linear-gradient(135deg, #ffd1b3, #ff8caa)" }} />
      <div className="aspect-square rounded" style={{ background: "linear-gradient(135deg, #87e3a5, #c4a8ff)" }} />
      <div className="aspect-square rounded" style={{ background: "linear-gradient(135deg, #87cefa, #87e3a5)" }} />
      <div className="aspect-square rounded" style={{ background: "linear-gradient(135deg, #ffd060, #ff8caa)" }} />
    </div>
  );
}

function AskIllu() {
  return (
    <div className="w-40 rounded-md border border-[var(--line)] bg-[var(--bg)] p-2">
      <div className="flex items-center gap-2 text-[10px] text-[var(--ink-muted)]">
        <span className="rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[8px] font-bold text-white">Q</span>
        <span>What did the coach say at halftime?</span>
      </div>
    </div>
  );
}

function JumpIllu() {
  return (
    <div className="w-40">
      <div className="h-3 rounded bg-[#e5e1d6] relative overflow-hidden">
        <span className="absolute top-0 bottom-0" style={{ left: "44%", width: "12%", background: "linear-gradient(90deg, #ff8caa, #7a4dff)" }} />
        <span className="absolute -top-1 -bottom-1" style={{ left: "48%", width: 2, background: "#0a0a0a" }} />
      </div>
      <div className="mt-1 text-[10px] font-mono text-[var(--ink-muted)]">02:14</div>
    </div>
  );
}

export function HowItWorks() {
  const { t } = useTranslation();
  return (
    <section id="how-it-works" className="bg-[var(--bg)]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-center text-3xl font-semibold tracking-tight md:text-4xl">
          {t("landing.how.title")}
        </h2>
        <div className="mt-12 grid gap-8 md:grid-cols-3">
          <StepCard number={1} title={t("landing.how.step1.title")} body={t("landing.how.step1.body")} illustration={<UploadIllu />} />
          <StepCard number={2} title={t("landing.how.step2.title")} body={t("landing.how.step2.body")} illustration={<AskIllu />} />
          <StepCard number={3} title={t("landing.how.step3.title")} body={t("landing.how.step3.body")} illustration={<JumpIllu />} />
        </div>
      </div>
    </section>
  );
}

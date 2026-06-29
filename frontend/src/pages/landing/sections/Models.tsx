import { useTranslation } from "react-i18next";

interface Model {
  name: string;
  roleKey: string;
  metric: string;
  metricLabel: string;
  blurbKey: string;
  dotClass: string;
}

const MODELS: Model[] = [
  {
    name: "Sprint",
    roleKey: "landing.models.viclip_role",
    metric: "768-d",
    metricLabel: "image-text embedding",
    blurbKey: "landing.models.viclip_blurb",
    dotClass: "bg-[#0447ff]",
  },
  {
    name: "Stride",
    roleKey: "landing.models.qddetr_role",
    metric: "58.9",
    metricLabel: "QVHighlights mAP",
    blurbKey: "landing.models.qddetr_blurb",
    dotClass: "bg-[#ff4704]",
  },
];

export function Models() {
  const { t } = useTranslation();
  return (
    <section id="models" className="mx-auto max-w-[1200px] scroll-mt-24 px-6 py-24">
      <header className="mb-12 text-center">
        <h2 className="text-[40px] font-light leading-[1.08] tracking-[-1px] text-[var(--color-obsidian)] md:text-[48px]">
          {t("landing.models.h2")}
        </h2>
        <p className="mx-auto mt-5 max-w-[560px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          {t("landing.models.sub")}
        </p>
      </header>

      <div className="grid gap-5 md:grid-cols-2">
        {MODELS.map((m) => (
          <div
            key={m.name}
            className="rounded-[24px] border border-[var(--color-chalk)] bg-white p-7 shadow-hairline"
          >
            <div className="flex items-center gap-3">
              <span className={`h-2.5 w-2.5 rounded-full ${m.dotClass}`} aria-hidden="true" />
              <h3 className="text-[18px] font-medium text-[var(--color-obsidian)]">{m.name}</h3>
            </div>
            <p className="mt-1 text-[13px] uppercase tracking-[0.12em] text-[var(--color-gravel)]">
              {t(m.roleKey)}
            </p>
            <p className="mt-5 text-[14px] leading-[1.55] text-[var(--color-gravel)]">{t(m.blurbKey)}</p>
            <div className="mt-6 flex items-baseline gap-2 border-t border-[var(--color-chalk)] pt-5">
              <span className="font-mono text-[28px] tracking-[-0.4px] text-[var(--color-obsidian)]">
                {m.metric}
              </span>
              <span className="text-[12px] uppercase tracking-[0.12em] text-[var(--color-gravel)]">
                {m.metricLabel}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

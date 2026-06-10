import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function CallToAction() {
  const { t } = useTranslation();
  return (
    <section id="cta" className="mx-auto max-w-[1200px] px-6 pb-24 pt-12">
      <div className="rounded-[32px] bg-gradient-warm px-8 py-20 text-center md:py-24">
        <h2 className="mx-auto max-w-[760px] text-[40px] font-light leading-[1.05] tracking-[-1px] text-[var(--color-obsidian)] md:text-[56px]">
          {t("landing.cta.h2")}
        </h2>
        <p className="mx-auto mt-5 max-w-[560px] text-[15px] leading-[1.55] text-[var(--color-gravel)]">
          {t("landing.cta.sub")}
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/signup"
            className="inline-flex h-11 items-center rounded-full bg-[var(--color-obsidian)] px-6 text-[14px] font-medium text-white transition duration-150 ease-out hover:bg-neutral-800 active:scale-[0.97]"
          >
            {t("landing.cta.try_playground")}
          </Link>
          <Link
            to="/pricing"
            className="inline-flex h-11 items-center rounded-full border border-[var(--color-chalk)] bg-white px-6 text-[14px] font-medium text-[var(--color-obsidian)] transition duration-150 ease-out hover:bg-[var(--color-powder)] active:scale-[0.97]"
          >
            {t("landing.cta.talk_to_sales")}
          </Link>
        </div>
      </div>
    </section>
  );
}

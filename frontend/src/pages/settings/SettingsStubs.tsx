import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";

interface StubProps {
  title: string;
  body: string;
}

function Stub({ title, body }: StubProps) {
  return (
    <section className="flex w-full flex-col gap-4 rounded-[32px] border border-[var(--color-chalk)] bg-white p-9">
      <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">{title}</p>
      <div className="flex items-start gap-2 rounded-xl border border-[var(--color-chalk)] bg-[var(--color-powder)] p-4 text-[13px] text-[var(--color-gravel)]">
        <Info size={16} className="mt-0.5 shrink-0" />
        <span>{body}</span>
      </div>
    </section>
  );
}

export function Organization() {
  const { t } = useTranslation();
  return <Stub title={t("settings.stubs.organization_title")} body={t("settings.stubs.organization_body")} />;
}
export function APIKeysPage() {
  const { t } = useTranslation();
  return <Stub title={t("settings.stubs.api_keys_title")} body={t("settings.stubs.api_keys_body")} />;
}
export function Usage() {
  const { t } = useTranslation();
  return <Stub title={t("settings.stubs.usage_title")} body={t("settings.stubs.usage_body")} />;
}
export function RateLimits() {
  const { t } = useTranslation();
  return <Stub title={t("settings.stubs.rate_limits_title")} body={t("settings.stubs.rate_limits_body")} />;
}
export function Webhooks() {
  const { t } = useTranslation();
  return <Stub title={t("settings.stubs.webhooks_title")} body={t("settings.stubs.webhooks_body")} />;
}
export function ProfilePage() {
  const { t } = useTranslation();
  return <Stub title={t("settings.stubs.profile_title")} body={t("settings.stubs.profile_body")} />;
}

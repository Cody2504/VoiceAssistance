import { Info } from "lucide-react";

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
  return <Stub title="Organization" body="Multi-member organization controls coming soon. For now your videos sit in your personal workspace." />;
}
export function APIKeysPage() {
  return <Stub title="API keys" body="Programmatic access tokens for the tl-jockey REST API. Issue, rotate, and revoke keys here once the IAM service exposes them." />;
}
export function Usage() {
  return <Stub title="Usage" body="Per-month breakdown of indexing minutes vs. analyze/segment requests will render here once metering wires up to the token-usage service." />;
}
export function RateLimits() {
  return <Stub title="Rate limits" body="Free plan ships with 60 requests / minute. View, request raises, or upgrade for higher caps." />;
}
export function Webhooks() {
  return <Stub title="Webhooks" body="Subscribe an HTTPS endpoint to ingest, ground, and edit completion events. Enable when the queue worker exposes its event stream." />;
}
export function ProfilePage() {
  return <Stub title="Profile" body="Display name, avatar, and email preferences. Edit your account details here." />;
}

import type { ReactNode } from "react";

interface Props {
  title: string;
  body: string;
  illustration: ReactNode;
}

export function FeatureCard({ title, body, illustration }: Props) {
  return (
    <article className="flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--line)] bg-white p-6 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex h-28 items-center justify-center rounded-[var(--radius-md)] bg-[var(--bg)]">
        {illustration}
      </div>
      <div>
        <h3 className="text-lg font-semibold tracking-tight text-[var(--ink)]">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-[var(--ink-soft)]">{body}</p>
      </div>
    </article>
  );
}

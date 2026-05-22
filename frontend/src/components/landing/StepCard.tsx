import type { ReactNode } from "react";

interface Props {
  number: 1 | 2 | 3;
  title: string;
  body: string;
  illustration: ReactNode;
}

export function StepCard({ number, title, body, illustration }: Props) {
  return (
    <article className="flex flex-col gap-3">
      <div className="flex h-24 items-center justify-center rounded-[var(--radius-md)] bg-white border border-[var(--line)]">
        {illustration}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold tracking-tight gradient-text">0{number}</span>
        <h3 className="text-base font-semibold tracking-tight text-[var(--ink)]">{title}</h3>
      </div>
      <p className="text-sm leading-relaxed text-[var(--ink-soft)]">{body}</p>
    </article>
  );
}

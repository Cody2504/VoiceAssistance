interface Props {
  quote: string;
  attribution: string;
}

export function QuoteCard({ quote, attribution }: Props) {
  return (
    <figure
      className="rounded-[var(--radius-lg)] bg-white p-5 text-sm leading-relaxed text-[var(--ink-soft)] shadow-[0_12px_32px_rgba(0,0,0,0.08)]"
      style={{ maxWidth: 280 }}
    >
      <blockquote className="m-0 italic">&ldquo;{quote}&rdquo;</blockquote>
      <figcaption className="mt-3 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--ink-muted)] not-italic">
        {attribution}
      </figcaption>
    </figure>
  );
}

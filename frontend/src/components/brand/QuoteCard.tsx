interface Props {
  quote: string;
  attribution: string;
}

export function QuoteCard({ quote, attribution }: Props) {
  return (
    <figure
      className="rounded-[28px] bg-white p-9 text-center shadow-[0_28px_70px_-28px_rgba(0,0,0,0.22)]"
      style={{ maxWidth: 380 }}
    >
      <blockquote className="m-0 text-[18px] leading-[1.55] text-[var(--ink-soft)]">&ldquo;{quote}&rdquo;</blockquote>
      <figcaption className="mt-6 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--ink-muted)] not-italic">
        {attribution}
      </figcaption>
    </figure>
  );
}

import { cn } from "@/lib/utils";

interface Props {
  size?: number;
  className?: string;
}

/**
 * The Jockey gradient orb — same look as the sidebar logo's mark, without the wordmark.
 * Use this anywhere we'd otherwise show a "J" avatar so the assistant identity stays
 * consistent across the chat thread and brand surfaces.
 */
export function BrandAvatar({ size = 20, className }: Props) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block rounded-full", className)}
      style={{
        width: size,
        height: size,
        background:
          "radial-gradient(circle at 30% 30%, #ffd5e2, #c4a8ff 55%, #87e3a5)",
      }}
    />
  );
}

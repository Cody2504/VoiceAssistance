import { cn } from "@/lib/utils";

interface Props {
  size?: "sm" | "md";
  className?: string;
}

export function Logo({ size = "md", className }: Props) {
  const dim = size === "sm" ? "h-6" : "h-7";
  const mark = size === "sm" ? "h-6 w-6" : "h-7 w-7";
  const text = size === "sm" ? "text-base" : "text-lg";
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", text, dim, className)}>
      <span
        className={cn("relative grid place-items-center rounded-full", mark)}
        style={{
          background:
            "radial-gradient(circle at 30% 30%, #ffd5e2, #c4a8ff 55%, #87e3a5)",
        }}
        aria-hidden="true"
      />
      <span>Jockey</span>
    </span>
  );
}

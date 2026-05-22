import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "filled" | "ghost";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const variants: Record<Variant, string> = {
  filled:
    "bg-[var(--color-obsidian)] text-[var(--color-eggshell)] hover:bg-neutral-800 shadow-[rgba(0,0,0,0.08)_0_1px_2px_0,rgba(0,0,0,0.06)_0_2px_4px_0]",
  ghost:
    "bg-white text-[var(--color-obsidian)] border border-[var(--color-chalk)] hover:bg-[var(--color-powder)]",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-9 px-4 text-[14px]",
  lg: "h-10 px-5 text-[15px]",
};

export const PillButton = forwardRef<HTMLButtonElement, Props>(function PillButton(
  { className, variant = "filled", size = "md", leftIcon, rightIcon, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-[0.1px] transition disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {leftIcon}
      <span>{children}</span>
      {rightIcon}
    </button>
  );
});

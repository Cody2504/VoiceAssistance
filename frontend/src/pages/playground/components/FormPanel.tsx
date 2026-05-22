import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

/**
 * Left-column form container styled like the TwelveLabs reference: rounded
 * white card with a full-width pill-shaped run button at the bottom.
 */
export function FormPanel({
  children,
  runLabel = "Run",
  onRun,
  running = false,
  canRun = true,
  hint,
}: {
  children: ReactNode;
  runLabel?: string;
  onRun: () => void;
  running?: boolean;
  canRun?: boolean;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-5 rounded-[18px] border border-[var(--color-chalk)] bg-white p-5 shadow-hairline">
      {children}

      {hint && <p className="text-[11px] text-[var(--color-gravel)]">{hint}</p>}

      <button
        type="button"
        onClick={onRun}
        disabled={!canRun || running}
        className="mt-1 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-[var(--color-obsidian)] text-[14px] font-medium text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-[var(--color-chalk)] disabled:text-[var(--color-slate)]"
      >
        {running ? (
          <>
            <Loader2 size={14} className="animate-spin" /> Running…
          </>
        ) : (
          <>
            {runLabel}
            <kbd className="rounded bg-white/15 px-1 py-0.5 text-[10px] font-mono text-white/90">Ctrl+↵</kbd>
          </>
        )}
      </button>
    </div>
  );
}

/**
 * A labeled field row inside FormPanel.
 */
export function Field({
  label,
  hint,
  required = false,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline gap-1.5">
        <label className="font-mono text-[12px] text-[var(--color-obsidian)]">{label}</label>
        {required && <span className="text-[10px] text-rose-500">*</span>}
      </div>
      {children}
      {hint && <p className="text-[11px] text-[var(--color-gravel)]">{hint}</p>}
    </div>
  );
}

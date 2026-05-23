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
 * A labeled field row inside FormPanel. `type` renders a small TwelveLabs-style
 * type chip (STRING / ARRAY / ENUM / NUMBER / INTEGER) next to the label.
 */
export function Field({
  label,
  hint,
  required = false,
  type,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  type?: "STRING" | "ARRAY" | "ENUM" | "NUMBER" | "INTEGER";
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        <span className="cursor-help border-b border-dashed border-[var(--color-chalk)] font-mono text-[12px] text-[var(--color-obsidian)]">
          {label}
        </span>
        {type && (
          <span className="inline-flex max-h-[16px] items-center rounded border border-[var(--color-chalk)] px-1 py-[3px] text-[9px] uppercase leading-none tracking-[0.06em] text-[var(--color-gravel)]">
            {type}
          </span>
        )}
        {required && <span className="font-mono text-[12px] text-rose-500">*</span>}
      </div>
      {children}
      {hint && <p className="text-[11px] text-[var(--color-gravel)]">{hint}</p>}
    </div>
  );
}

/**
 * Filled-square checkbox matching the TwelveLabs `bg-grey-700 + white check`
 * pattern used in search_options / transcription_options.
 */
export function CheckOption({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-1.5 pr-1">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-[4px] border border-[var(--color-chalk)] bg-white text-white transition peer-checked:border-[var(--color-obsidian)] peer-checked:bg-[var(--color-obsidian)]">
        {checked && (
          <svg viewBox="0 0 16 16" width={12} height={12} fill="none" aria-hidden="true">
            <path d="M3.5 8.5l3 3 6-7" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      <span className="text-[13px] text-[var(--color-obsidian)]">{label}</span>
    </label>
  );
}

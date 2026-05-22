import { useState, type ReactNode } from "react";
import { ChevronDown, RotateCcw } from "lucide-react";

/**
 * Collapsible "Advanced Settings" group inside a FormPanel. Mirrors the
 * pattern from the TwelveLabs playground (label + reset link + expandable body).
 */
export function AdvancedSettings({
  children,
  onReset,
}: {
  children: ReactNode;
  onReset?: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-neutral-200 pt-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-neutral-800 hover:text-neutral-950"
        >
          Advanced Settings
          <ChevronDown
            className={`h-3.5 w-3.5 text-neutral-500 transition ${open ? "rotate-180" : ""}`}
          />
        </button>
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-800"
          >
            <RotateCcw className="h-3 w-3" /> Reset
          </button>
        )}
      </div>

      {open && <div className="mt-4 space-y-4">{children}</div>}
    </div>
  );
}

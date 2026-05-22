import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export interface DropdownItem {
  value: string;
  label: string;
  description?: string;
  badge?: string;
}

interface Props {
  items: DropdownItem[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

/**
 * Two-line dropdown matching the TwelveLabs MUI Select shape:
 * trigger shows the selected label; menu items render a `label` (body) plus
 * an optional `description` (subdued small text).
 */
export function PrettyDropdown({
  items,
  value,
  onChange,
  placeholder = "Select…",
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = items.find((i) => i.value === value) ?? null;

  return (
    <div ref={wrapRef} className={cn("relative", className)}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-neutral-300 bg-white px-3 text-left text-[13px] text-neutral-900 transition hover:border-neutral-500 focus:border-neutral-700 focus:outline-none"
      >
        <span className="truncate">
          {selected ? selected.label : placeholder}
          {selected?.badge ? (
            <span className="ml-2 rounded border border-neutral-300 px-1 font-mono text-[10px] text-neutral-500">
              {selected.badge}
            </span>
          ) : null}
        </span>
        <ChevronDown size={14} className="shrink-0 text-neutral-500" />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-neutral-200 bg-white py-1 shadow-[0_4px_16px_0_rgba(28,29,27,0.18)]"
        >
          {items.map((item) => {
            const isSelected = item.value === value;
            return (
              <li key={item.value} role="option" aria-selected={isSelected}>
                <button
                  type="button"
                  onClick={() => {
                    onChange(item.value);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full flex-col gap-0.5 px-3 py-2 text-left transition hover:bg-neutral-100",
                    isSelected && "bg-neutral-100",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span className="text-[13px] text-neutral-900">{item.label}</span>
                    {item.badge && (
                      <span className="rounded border border-neutral-300 px-1 font-mono text-[10px] text-neutral-500">
                        {item.badge}
                      </span>
                    )}
                  </span>
                  {item.description && (
                    <span className="text-[10px] leading-[14px] text-neutral-500">
                      {item.description}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

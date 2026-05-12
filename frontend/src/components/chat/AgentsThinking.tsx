import { useState } from "react";
import { ChevronDown, ListChecks } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ThinkingStep {
  type: "thought" | "tool_call" | "tool_result";
  agent?: string;
  text?: string;
  tool?: string;
  args?: unknown;
  result?: unknown;
}

interface Props {
  steps: ThinkingStep[];
}

export function AgentsThinking({ steps }: Props) {
  const [open, setOpen] = useState(false);
  if (steps.length === 0) return null;

  const count = steps.length;

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-neutral-900 hover:bg-neutral-50"
      >
        <span className="flex items-center gap-2">
          <ListChecks size={16} className="text-neutral-600" />
          Agents Thinking
        </span>
        <span className="flex items-center gap-2 text-xs text-neutral-500">
          {count} {count === 1 ? "step" : "steps"}
          <ChevronDown size={14} className={cn("transition", open && "rotate-180")} />
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-neutral-200 bg-neutral-50/60 px-4 py-3 text-xs">
          {steps.map((s, i) => {
            if (s.type === "thought") {
              return (
                <div key={i} className="text-neutral-700">
                  <span className="mr-2 inline-block rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-[10px] uppercase text-neutral-700">
                    {s.agent ?? "agent"}
                  </span>
                  {s.text}
                </div>
              );
            }
            if (s.type === "tool_call") {
              return (
                <div key={i} className="rounded border border-amber-200 bg-amber-50 p-2">
                  <span className="font-mono text-[10px] uppercase text-amber-700">→ {s.tool}</span>
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-neutral-700">{JSON.stringify(s.args, null, 2)}</pre>
                </div>
              );
            }
            return (
              <div key={i} className="rounded border border-emerald-200 bg-emerald-50 p-2">
                <span className="font-mono text-[10px] uppercase text-emerald-700">← {s.tool}</span>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-neutral-700">{JSON.stringify(s.result, null, 2)}</pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

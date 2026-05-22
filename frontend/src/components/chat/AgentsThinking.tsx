import { useState } from "react";
import { ChevronDown, ChevronRight, ListChecks } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ThinkingStep {
  type: "thought" | "tool_call" | "tool_result";
  agent?: string;
  text?: string;
  tool?: string;
  args?: unknown;
  result?: unknown;
}

type StepStatus = "active" | "done" | "error";

type DerivedStep =
  | { kind: "phase"; key: string; label: string; status: StepStatus; body?: string }
  | { kind: "tool"; key: string; label: string; status: StepStatus; tool: string; args: unknown; result?: unknown };

interface Props {
  steps: ThinkingStep[];
  assistantHasContent: boolean;
  complete: boolean;
}

function fmtSec(s: number): string {
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

function toolLabel(name: string | undefined, args: unknown): string {
  if (!name) return "Tool call";
  const a = (args ?? {}) as Record<string, unknown>;
  switch (name) {
    case "search_corpus":
    case "video-search":
      return "Searching the corpus";
    case "search_video_local":
      return "Searching one video";
    case "ask_video_local":
      if (typeof a.t_start === "number" && typeof a.t_end === "number") {
        return `Reading transcript ${fmtSec(a.t_start)}–${fmtSec(a.t_end)}`;
      }
      return "Summarizing the video";
    case "time-range-analysis":
      if (typeof a.t_start === "number" && typeof a.t_end === "number") {
        return `Reading transcript ${fmtSec(a.t_start)}–${fmtSec(a.t_end)}`;
      }
      return "Reading transcript";
    case "gist-text-generation":
    case "summarize-text-generation":
    case "free-text-generation":
      return "Summarizing the video";
    default:
      return name;
  }
}

function agentPhaseLabel(agent?: string): string {
  if (agent === "planner") return "Understanding your request";
  if (agent === "supervisor" || agent === "instructor") return "Choosing a worker";
  return "Thinking";
}

function isErrorResult(r: unknown): boolean {
  if (!r || typeof r !== "object") return false;
  const o = r as Record<string, unknown>;
  if (typeof o.error === "string" && o.error.length > 0) return true;
  if (typeof o.status === "string" && o.status === "error") return true;
  return false;
}

export function deriveSteps(
  raw: ThinkingStep[],
  assistantHasContent: boolean,
  complete: boolean,
): DerivedStep[] {
  const out: DerivedStep[] = [];

  raw.forEach((s, i) => {
    if (s.type === "thought") {
      const label = agentPhaseLabel(s.agent);
      const prev = out[out.length - 1];
      if (prev && prev.kind === "phase" && prev.label === label) {
        prev.body = (prev.body ?? "") + (s.text ?? "");
      } else {
        out.push({ kind: "phase", key: `s-${i}`, label, status: "done", body: s.text });
      }
    } else if (s.type === "tool_call") {
      out.push({
        kind: "tool",
        key: `s-${i}`,
        label: toolLabel(s.tool, s.args),
        status: "active",
        tool: s.tool ?? "?",
        args: s.args,
      });
    } else if (s.type === "tool_result") {
      for (let j = out.length - 1; j >= 0; j--) {
        const x = out[j];
        if (x.kind === "tool" && x.tool === s.tool && x.status === "active") {
          x.result = s.result;
          x.status = isErrorResult(s.result) ? "error" : "done";
          break;
        }
      }
    }
  });

  if (assistantHasContent && out.length > 0) {
    out.push({ kind: "phase", key: "reply", label: "Composing reply", status: "done" });
  }

  if (!complete && out.length > 0) {
    const last = out[out.length - 1];
    if (last.status !== "error") last.status = "active";
  }

  return out;
}

export function AgentsThinking({ steps, assistantHasContent, complete }: Props) {
  const derived = deriveSteps(steps, assistantHasContent, complete);
  const [open, setOpen] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  if (derived.length === 0) return null;
  const count = derived.length;

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-neutral-900 hover:bg-neutral-50"
      >
        <span className="flex items-center gap-2">
          <ListChecks size={16} className="text-neutral-600" />
          {complete ? "Agents Thinking" : "Agents Thinking…"}
        </span>
        <span className="flex items-center gap-2 text-xs text-neutral-500">
          {count} {count === 1 ? "step" : "steps"}
          <ChevronDown size={14} className={cn("transition", open && "rotate-180")} />
        </span>
      </button>

      {open && (
        <ol className="relative space-y-1 border-t border-neutral-200 px-4 py-3 text-sm">
          <div
            className="pointer-events-none absolute bottom-4 left-[26px] top-4 w-px bg-neutral-200"
            aria-hidden
          />
          {derived.map((s) => (
            <StepRow
              key={s.key}
              step={s}
              expanded={!!expanded[s.key]}
              onToggle={() => setExpanded((m) => ({ ...m, [s.key]: !m[s.key] }))}
            />
          ))}
        </ol>
      )}
    </div>
  );
}

function StatusDot({ status }: { status: StepStatus }) {
  if (status === "active") {
    return (
      <span className="relative inline-flex h-3 w-3" data-testid="dot-active">
        <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/60" />
        <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500" />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span
        className="inline-flex h-3 w-3 rounded-full border-2 border-red-500 bg-white"
        data-testid="dot-error"
      />
    );
  }
  return (
    <span
      className="inline-flex h-3 w-3 rounded-full border-2 border-neutral-300 bg-white"
      data-testid="dot-done"
    />
  );
}

function StepRow({
  step,
  expanded,
  onToggle,
}: {
  step: DerivedStep;
  expanded: boolean;
  onToggle: () => void;
}) {
  const hasBody = step.kind === "phase" ? Boolean(step.body) : true;
  return (
    <li className="relative pl-7">
      <div className="absolute left-[14px] top-2 -translate-x-1/2">
        <StatusDot status={step.status} />
      </div>
      <button
        type="button"
        onClick={hasBody ? onToggle : undefined}
        className={cn(
          "flex w-full items-center justify-between rounded px-1.5 py-1 text-left",
          hasBody && "hover:bg-neutral-50",
        )}
        data-step-label={step.label}
      >
        <span
          className={cn(
            "truncate text-neutral-800",
            step.status === "active" && "font-medium text-neutral-900",
          )}
        >
          {step.label}
        </span>
        {hasBody && (
          <span className="ml-2 shrink-0 text-neutral-400">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        )}
      </button>
      {expanded && hasBody && (
        <div className="ml-1.5 mt-1 rounded border border-neutral-100 bg-neutral-50/60 p-2 text-xs text-neutral-700">
          {step.kind === "phase" ? (
            <p className="whitespace-pre-wrap">{step.body}</p>
          ) : (
            <div className="space-y-2">
              <div>
                <div className="mb-1 font-mono text-[10px] uppercase text-neutral-500">args</div>
                <pre className="overflow-x-auto whitespace-pre-wrap">{JSON.stringify(step.args, null, 2)}</pre>
              </div>
              {step.result !== undefined && (
                <div>
                  <div className="mb-1 font-mono text-[10px] uppercase text-neutral-500">result</div>
                  <pre className="overflow-x-auto whitespace-pre-wrap">{JSON.stringify(step.result, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

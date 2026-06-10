import { useState } from "react";
import { useTranslation } from "react-i18next";
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

type TFn = (key: string, opts?: Record<string, unknown>) => string;

function toolLabel(name: string | undefined, args: unknown, t: TFn): string {
  if (!name) return t("chat.thinking.tool_default");
  const a = (args ?? {}) as Record<string, unknown>;
  switch (name) {
    case "search_corpus":
    case "video-search":
      return t("chat.thinking.tool_search_corpus");
    case "search_video_local":
      return t("chat.thinking.tool_search_video");
    case "ask_video_local":
      if (typeof a.t_start === "number" && typeof a.t_end === "number") {
        return t("chat.thinking.tool_transcript_range", { start: fmtSec(a.t_start), end: fmtSec(a.t_end) });
      }
      return t("chat.thinking.tool_summarize");
    case "time-range-analysis":
      if (typeof a.t_start === "number" && typeof a.t_end === "number") {
        return t("chat.thinking.tool_transcript_range", { start: fmtSec(a.t_start), end: fmtSec(a.t_end) });
      }
      return t("chat.thinking.tool_read_transcript");
    case "gist-text-generation":
    case "summarize-text-generation":
    case "free-text-generation":
      return t("chat.thinking.tool_summarize");
    default:
      return name;
  }
}

function agentPhaseLabel(agent: string | undefined, t: TFn): string {
  if (agent === "planner") return t("chat.thinking.phase_planner");
  if (agent === "supervisor" || agent === "instructor") return t("chat.thinking.phase_supervisor");
  return t("chat.thinking.phase_default");
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
  t: TFn,
): DerivedStep[] {
  const out: DerivedStep[] = [];

  raw.forEach((s, i) => {
    if (s.type === "thought") {
      const label = agentPhaseLabel(s.agent, t);
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
        label: toolLabel(s.tool, s.args, t),
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
    out.push({ kind: "phase", key: "reply", label: t("chat.thinking.phase_composing"), status: "done" });
  }

  if (!complete && out.length > 0) {
    const last = out[out.length - 1];
    if (last.status !== "error") last.status = "active";
  }

  return out;
}

export function AgentsThinking({ steps, assistantHasContent, complete }: Props) {
  const { t } = useTranslation();
  const derived = deriveSteps(steps, assistantHasContent, complete, t as TFn);
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
          {complete ? t("chat.thinking.header") : t("chat.thinking.header_active")}
        </span>
        <span className="flex items-center gap-2 text-xs text-neutral-500">
          {t(count === 1 ? "chat.thinking.step_count_one" : "chat.thinking.step_count_other", { count })}
          <ChevronDown size={14} className={cn("transition", open && "rotate-180")} />
        </span>
      </button>

      {/* grid-rows 0fr→1fr animates the panel height smoothly (no snap) */}
      <div
        className={cn(
          "grid transition-[grid-template-rows,opacity] duration-200 ease-out",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        )}
      >
        <div className="overflow-hidden">
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
                t={t as TFn}
              />
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: StepStatus }) {
  if (status === "active") {
    // Subtle: a small solid dot with a faint static halo (no loud ping).
    return (
      <span
        className="block h-2 w-2 rounded-full bg-emerald-500 ring-[3px] ring-emerald-500/15"
        data-testid="dot-active"
      />
    );
  }
  if (status === "error") {
    return (
      <span
        className="block h-2 w-2 rounded-full border border-red-400 bg-white"
        data-testid="dot-error"
      />
    );
  }
  return (
    <span
      className="block h-2 w-2 rounded-full border border-neutral-300 bg-white"
      data-testid="dot-done"
    />
  );
}

function StepRow({
  step,
  expanded,
  onToggle,
  t,
}: {
  step: DerivedStep;
  expanded: boolean;
  onToggle: () => void;
  t: TFn;
}) {
  const hasBody = step.kind === "phase" ? Boolean(step.body) : true;
  return (
    <li className="relative pl-7">
      <div className="absolute left-[10px] top-2.5 -translate-x-1/2">
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
            "truncate text-neutral-700",
            step.status === "active" && "text-neutral-900",
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
      <div
        className={cn(
          "grid transition-[grid-template-rows,opacity] duration-200 ease-out",
          expanded && hasBody ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        )}
      >
        <div className="overflow-hidden">
          <div className="ml-1.5 mt-1 rounded border border-neutral-100 bg-neutral-50/60 p-2 text-xs text-neutral-700">
            {step.kind === "phase" ? (
              <p className="whitespace-pre-wrap">{step.body}</p>
            ) : (
              <div className="space-y-2">
                <div>
                  <div className="mb-1 font-mono text-[10px] uppercase text-neutral-500">{t("chat.thinking.args_label")}</div>
                  <pre className="overflow-x-auto whitespace-pre-wrap">{JSON.stringify(step.args, null, 2)}</pre>
                </div>
                {step.result !== undefined && (
                  <div>
                    <div className="mb-1 font-mono text-[10px] uppercase text-neutral-500">{t("chat.thinking.result_label")}</div>
                    <pre className="overflow-x-auto whitespace-pre-wrap">{JSON.stringify(step.result, null, 2)}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

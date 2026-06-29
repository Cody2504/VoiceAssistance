import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";

import { createEvalRun, editEvalCase, type EvalCaseRow } from "@/apis/admin.api";
import { useEvalRunQuery, useEvalRunsQuery, qk } from "@/apis/queries";

function fmt(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}

export default function AdminEvaluation() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data: runs, isError } = useEvalRunsQuery();
  const [selectedRun, setSelectedRun] = useState<string | undefined>(undefined);
  const { data: detail } = useEvalRunQuery(selectedRun);

  const [picked, setPicked] = useState<Set<string>>(new Set()); // golden_ids selected to re-run
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState<EvalCaseRow | null>(null);

  useEffect(() => {
    if (!selectedRun && runs && runs.length > 0) setSelectedRun(runs[0].id);
  }, [runs, selectedRun]);
  // Clear the selection when switching runs.
  useEffect(() => setPicked(new Set()), [selectedRun]);

  const running = (runs ?? []).some((r) => r.status === "running");
  const cases = detail?.cases ?? [];
  const selectableIds = cases.map((c) => c.golden_id).filter((g): g is string => !!g);
  const allPicked = selectableIds.length > 0 && selectableIds.every((g) => picked.has(g));

  function toggle(goldenId: string) {
    setPicked((s) => {
      const next = new Set(s);
      next.has(goldenId) ? next.delete(goldenId) : next.add(goldenId);
      return next;
    });
  }
  function toggleAll() {
    setPicked(allPicked ? new Set() : new Set(selectableIds));
  }

  async function run(goldenIds?: string[]) {
    setMenuOpen(false);
    await createEvalRun({ kind: "curated", mode: "fake", judge: true, golden_ids: goldenIds });
    await queryClient.invalidateQueries({ queryKey: qk.evalRuns() });
  }

  const s = detail?.run.summary;

  return (
    <div className="px-8 py-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-semibold">{t("admin.evaluation.title")}</h1>
        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            disabled={running}
            className="rounded-md border border-[var(--color-obsidian)] px-3 py-1.5 text-sm disabled:opacity-40"
          >
            {running ? t("admin.evaluation.running") : `${t("admin.evaluation.run")} ▾`}
          </button>
          {menuOpen && !running && (
            <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-[var(--color-chalk)] bg-white py-1 shadow-lg">
              <button
                type="button"
                onClick={() => void run()}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-eggshell)]"
              >
                {t("admin.evaluation.run_full")}
              </button>
              <button
                type="button"
                disabled={picked.size === 0}
                onClick={() => void run([...picked])}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-eggshell)] disabled:opacity-40"
              >
                {t("admin.evaluation.run_selected", { count: picked.size })}
              </button>
            </div>
          )}
        </div>
      </div>

      {isError && <p className="mt-6 text-sm text-[var(--color-gravel)]">{t("admin.evaluation.error")}</p>}

      {/* Run history */}
      <div className="mt-6 flex flex-wrap gap-2">
        {(runs ?? []).map((r, i, arr) => (
          <button
            key={r.id}
            onClick={() => setSelectedRun(r.id)}
            className={`rounded-md border px-3 py-1.5 text-xs ${selectedRun === r.id ? "border-[var(--color-obsidian)]" : "border-[var(--color-chalk)]"}`}
          >
            {t("admin.evaluation.run_label")} #{arr.length - i}
            {r.summary ? ` · F1 ${fmt(r.summary.routing_f1_macro)}` : ` · ${r.status}`}
            {r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString()}` : ""}
          </button>
        ))}
        {runs && runs.length === 0 && (
          <p className="text-sm text-[var(--color-gravel)]">{t("admin.evaluation.no_runs")}</p>
        )}
      </div>

      {/* Summary cards */}
      {s && (
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            [t("admin.evaluation.summary_f1"), fmt(s.routing_f1_macro)],
            [t("admin.evaluation.summary_arg"), fmt(s.arg_correctness_rate)],
            [t("admin.evaluation.summary_task"), fmt(s.mean_task_completion)],
            [t("admin.evaluation.summary_answer"), fmt(s.mean_answer_relevancy)],
          ].map(([label, val]) => (
            <div key={label} className="rounded-lg border border-[var(--color-chalk)] p-4">
              <div className="text-xs text-[var(--color-gravel)]">{label}</div>
              <div className="mt-1 text-2xl font-semibold">{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Per-case table */}
      {detail && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full whitespace-nowrap text-sm">
            <thead className="text-left text-[var(--color-gravel)]">
              <tr>
                <th className="py-2 pr-3">
                  <input type="checkbox" checked={allPicked} onChange={toggleAll} disabled={selectableIds.length === 0} />
                </th>
                <th className="py-2 pr-4">{t("admin.evaluation.col_query")}</th>
                <th className="py-2 pr-4">{t("admin.evaluation.col_expected")}</th>
                <th className="py-2 pr-4">{t("admin.evaluation.col_predicted")}</th>
                <th className="py-2 px-3 text-center">{t("admin.evaluation.col_tool")}</th>
                <th className="py-2 px-3 text-center">{t("admin.evaluation.col_arg")}</th>
                <th className="py-2 px-3 text-center">{t("admin.evaluation.col_task")}</th>
                <th className="py-2 px-3 text-center">{t("admin.evaluation.col_answer")}</th>
                <th className="py-2 px-3 text-center">{t("admin.evaluation.col_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id} className="border-t border-[var(--color-chalk)]">
                  <td className="py-2 pr-3">
                    {c.golden_id && (
                      <input type="checkbox" checked={picked.has(c.golden_id)} onChange={() => toggle(c.golden_id!)} />
                    )}
                  </td>
                  <td className="py-2 pr-4">{c.query}</td>
                  <td className="py-2 pr-4">{c.expected_tool ?? "—"}</td>
                  <td className="py-2 pr-4">{c.predicted_tool ?? "—"}</td>
                  <td className="py-2 px-3 text-center">{c.tool_correct === null ? "—" : c.tool_correct ? "✓" : "✗"}</td>
                  <td className="py-2 px-3 text-center">{c.arg_ok === null ? "—" : c.arg_ok ? "✓" : "✗"}</td>
                  <td className="py-2 px-3 text-center">{fmt(c.task_completion)}</td>
                  <td className="py-2 px-3 text-center">{fmt(c.answer_relevancy)}</td>
                  <td className="py-2 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => setEditing(c)}
                      className="text-xs text-[var(--color-accent-blue)] hover:underline"
                    >
                      {t("admin.evaluation.edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <CaseEditModal
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await queryClient.invalidateQueries({ queryKey: qk.evalRun(selectedRun) });
          }}
        />
      )}
    </div>
  );
}

function CaseEditModal({
  row,
  onClose,
  onSaved,
}: {
  row: EvalCaseRow;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [tool, setTool] = useState(row.expected_tool ?? "");
  const [argsText, setArgsText] = useState(row.expected_args ? JSON.stringify(row.expected_args, null, 2) : "");
  const [answer, setAnswer] = useState(row.reference_answer ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    let parsedArgs: Record<string, unknown> | null = null;
    if (argsText.trim()) {
      try {
        parsedArgs = JSON.parse(argsText);
      } catch {
        setError(t("admin.evaluation.bad_json"));
        setSaving(false);
        return;
      }
    }
    try {
      await editEvalCase(row.id, {
        expected_tool: tool.trim(),
        expected_args: parsedArgs,
        reference_answer: answer.trim() ? answer : null,
      });
      await onSaved();
    } catch {
      setError(t("admin.evaluation.save_error"));
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-[18px] font-semibold">{t("admin.evaluation.edit_title")}</h2>
        <p className="mt-1 truncate text-[12px] text-[var(--color-gravel)]">{row.query}</p>

        <label className="mt-4 block text-[12px] font-medium text-[var(--color-gravel)]">
          {t("admin.evaluation.col_expected")}
          <input
            value={tool}
            onChange={(e) => setTool(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--color-chalk)] px-3 py-2 text-[13px]"
          />
        </label>

        <label className="mt-3 block text-[12px] font-medium text-[var(--color-gravel)]">
          {t("admin.evaluation.expected_args")}
          <textarea
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            rows={4}
            placeholder="{ }"
            className="mt-1 w-full rounded-lg border border-[var(--color-chalk)] px-3 py-2 font-mono text-[12px]"
          />
        </label>

        <label className="mt-3 block text-[12px] font-medium text-[var(--color-gravel)]">
          {t("admin.evaluation.reference_answer")}
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-[var(--color-chalk)] px-3 py-2 text-[13px]"
          />
        </label>

        {error && <p className="mt-3 text-[12px] text-red-600">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg border border-[var(--color-chalk)] px-4 py-2 text-[13px]">
            {t("admin.evaluation.cancel")}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-[var(--color-obsidian)] px-4 py-2 text-[13px] text-white disabled:opacity-40"
          >
            {saving ? t("admin.evaluation.saving") : t("admin.evaluation.save")}
          </button>
        </div>
      </div>
    </div>
  );
}

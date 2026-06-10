/**
 * SegmentBuilderModal — visual editor for segment definitions.
 *
 * Lets the user author definitions (id + description + image + fields) without
 * writing JSON. Each field has name / type / description / enum, matching the
 * backend `SegmentDefinition` schema. Round-trips with the JSON view: it reads
 * the current definitions on open and emits the edited array via onChange.
 */
import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { SegmentDefinition, SegmentFieldSpec } from "@/apis/videos.api";

interface SegmentBuilderModalProps {
  open: boolean;
  value: unknown[];
  onChange: (next: SegmentDefinition[]) => void;
  onClose: () => void;
}

type FieldType = "string" | "number" | "boolean";

function emptyField(): SegmentFieldSpec {
  return { name: "", type: "string", description: "", enum: [] };
}

function emptyDef(): SegmentDefinition {
  return { id: "", description: "", fields: [] };
}

function coerceDefs(value: unknown[]): SegmentDefinition[] {
  if (!Array.isArray(value)) return [emptyDef()];
  const defs = value
    .filter((d): d is Record<string, unknown> => typeof d === "object" && d !== null)
    .map((d) => ({
      id: String(d.id ?? ""),
      description: String(d.description ?? ""),
      fields: Array.isArray(d.fields)
        ? (d.fields as Record<string, unknown>[]).map((f) => ({
            name: String(f?.name ?? ""),
            type: (["string", "number", "boolean"].includes(String(f?.type)) ? f?.type : "string") as FieldType,
            description: String(f?.description ?? ""),
            enum: Array.isArray(f?.enum) ? (f.enum as unknown[]).map(String) : [],
          }))
        : [],
      time_ranges: Array.isArray(d.time_ranges) ? (d.time_ranges as unknown[]).map(String) : undefined,
      image_attachment: typeof d.image_attachment === "string" ? d.image_attachment : undefined,
    }));
  return defs.length ? defs : [emptyDef()];
}

export function SegmentBuilderModal({ open, value, onChange, onClose }: SegmentBuilderModalProps) {
  const { t } = useTranslation();
  const [defs, setDefs] = useState<SegmentDefinition[]>([]);

  useEffect(() => {
    if (open) setDefs(coerceDefs(value));
  }, [open, value]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const patchDef = (i: number, patch: Partial<SegmentDefinition>) =>
    setDefs((d) => d.map((def, idx) => (idx === i ? { ...def, ...patch } : def)));

  const patchField = (di: number, fi: number, patch: Partial<SegmentFieldSpec>) =>
    setDefs((d) =>
      d.map((def, idx) =>
        idx === di
          ? { ...def, fields: def.fields.map((f, j) => (j === fi ? { ...f, ...patch } : f)) }
          : def,
      ),
    );

  const apply = () => {
    // drop blank trailing fields; require an id per definition
    const cleaned = defs
      .map((d) => ({ ...d, fields: d.fields.filter((f) => f.name.trim()) }))
      .filter((d) => d.id.trim());
    onChange(cleaned);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("pgkit.segment_builder.title")}
      onClick={onClose}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-5xl flex-col gap-3 rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-[var(--color-obsidian)]">{t("pgkit.segment_builder.title")}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("pgkit.segment_builder.close")}
            className="rounded p-1 text-[var(--color-fog)] hover:bg-[var(--color-powder)] hover:text-[var(--color-obsidian)] focus-visible:outline-2 focus-visible:outline-signal"
          >
            <X size={16} />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-5 md:grid-cols-[minmax(320px,2fr)_minmax(0,3fr)]">
        {/* LEFT — Builder */}
        <div className="flex min-h-0 flex-col gap-3">
          <div className="text-[12px] font-semibold text-[var(--color-obsidian)]">{t("pgkit.segment_builder.builder_col")}</div>
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1 pb-2">
            {defs.map((def, di) => (
              <div key={di} className="flex flex-col rounded-lg border border-[var(--color-chalk)] bg-white">
                <div className="flex items-center justify-between gap-2 p-3">
                  <input
                    className="h-7 min-w-0 flex-1 rounded-md bg-transparent px-2 font-mono text-[12px] font-medium text-[var(--color-obsidian)] hover:bg-[var(--color-powder)] focus-visible:outline-2 focus-visible:outline-signal"
                    placeholder={t("pgkit.segment_builder.def_id_placeholder")}
                    value={def.id}
                    onChange={(e) => patchDef(di, { id: e.target.value })}
                    aria-label={t("pgkit.segment_builder.def_id_label")}
                  />
                  <span className="shrink-0 text-[11px] text-[var(--color-gravel)]">
                    {t(def.fields.length === 1 ? "pgkit.segment_builder.field_count_one" : "pgkit.segment_builder.field_count_other", { count: def.fields.length })}
                  </span>
                  <button
                    type="button"
                    aria-label={t("pgkit.segment_builder.remove_def")}
                    onClick={() => setDefs((d) => d.filter((_, idx) => idx !== di))}
                    className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[var(--color-gravel)] hover:bg-[var(--color-powder)] hover:text-[var(--color-obsidian)]"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>

                <div className="flex flex-col gap-4 px-3 pb-4 pt-1">
                  {/* Description */}
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase leading-3 text-[var(--color-gravel)]">{t("pgkit.segment_builder.description_label")}</span>
                      <span className="text-[10px] text-[var(--color-fog)]">{t("pgkit.segment_builder.description_char_count", { count: def.description.length })}</span>
                    </div>
                    <textarea
                      className="min-h-[56px] resize-none rounded-[8px] border border-[var(--color-chalk)] bg-white px-3 py-2 text-[12px] leading-5 text-[var(--color-obsidian)] focus:border-[var(--color-gravel)] focus:outline-none"
                      placeholder={t("pgkit.segment_builder.description_placeholder")}
                      value={def.description}
                      onChange={(e) => patchDef(di, { description: e.target.value.slice(0, 2000) })}
                      aria-label={t("pgkit.segment_builder.description_aria")}
                    />
                  </div>

                  {/* Fields */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase leading-3 text-[var(--color-gravel)]">{t("pgkit.segment_builder.fields_label")}</span>
                      <span className="text-[10px] text-[var(--color-fog)]">{t("pgkit.segment_builder.fields_count", { count: def.fields.length })}</span>
                    </div>
                    <div className="flex flex-col gap-2">
                      {def.fields.map((f, fi) => (
                        <div
                          key={fi}
                          className="group flex flex-col gap-2 rounded-lg border border-[var(--color-chalk)] bg-white p-2"
                        >
                          <div className="flex items-center gap-2">
                            <input
                              className="h-7 min-w-0 flex-1 rounded-md bg-transparent px-2 font-mono text-[12px] text-[var(--color-obsidian)] hover:bg-[var(--color-powder)] focus-visible:outline-2 focus-visible:outline-signal"
                              placeholder={t("pgkit.segment_builder.field_name_placeholder")}
                              value={f.name}
                              onChange={(e) => patchField(di, fi, { name: e.target.value })}
                              aria-label={t("pgkit.segment_builder.field_name_aria")}
                            />
                            <select
                              className="h-7 w-[100px] shrink-0 rounded-md border border-[var(--color-chalk)] bg-white px-2 text-[11px] text-[var(--color-gravel)] focus:outline-none"
                              value={f.type ?? "string"}
                              onChange={(e) => patchField(di, fi, { type: e.target.value as FieldType })}
                              aria-label={t("pgkit.segment_builder.field_type_aria")}
                            >
                              <option value="string">{t("pgkit.segment_builder.field_type_string")}</option>
                              <option value="number">{t("pgkit.segment_builder.field_type_number")}</option>
                              <option value="boolean">{t("pgkit.segment_builder.field_type_boolean")}</option>
                            </select>
                            <button
                              type="button"
                              aria-label={t("pgkit.segment_builder.remove_field")}
                              onClick={() => patchDef(di, { fields: def.fields.filter((_, j) => j !== fi) })}
                              className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[var(--color-gravel)] opacity-0 hover:bg-[var(--color-powder)] hover:text-[var(--color-obsidian)] group-hover:opacity-100"
                            >
                              <X size={13} />
                            </button>
                          </div>
                          <input
                            className="h-7 w-full rounded-md border border-[var(--color-chalk)] bg-white px-2 text-[11px] text-[var(--color-gravel)] placeholder:text-[var(--color-fog)] focus:border-[var(--color-gravel)] focus:outline-none"
                            placeholder={t("pgkit.segment_builder.field_enum_placeholder")}
                            value={(f.enum ?? []).join(", ")}
                            onChange={(e) =>
                              patchField(di, fi, {
                                enum: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                              })
                            }
                            aria-label={t("pgkit.segment_builder.field_enum_aria")}
                          />
                        </div>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => patchDef(di, { fields: [...def.fields, emptyField()] })}
                      className="inline-flex h-8 w-full items-center justify-center gap-1.5 rounded-[8px] bg-[var(--color-powder)] text-[12px] text-[var(--color-gravel)] transition-colors hover:bg-[var(--color-chalk)]"
                    >
                      <Plus size={13} /> {t("pgkit.segment_builder.add_field")}
                    </button>
                  </div>

                  {/* Time Ranges */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase leading-3 text-[var(--color-gravel)]">{t("pgkit.segment_builder.time_ranges_label")}</span>
                      <span className="text-[10px] text-[var(--color-fog)]">
                        {(def.time_ranges ?? []).length}
                      </span>
                    </div>
                    <input
                      className="h-8 w-full rounded-[8px] border border-[var(--color-chalk)] bg-white px-3 text-[12px] text-[var(--color-obsidian)] placeholder:text-[var(--color-fog)] focus:border-[var(--color-gravel)] focus:outline-none"
                      placeholder={t("pgkit.segment_builder.time_ranges_placeholder")}
                      value={(def.time_ranges ?? []).join(", ")}
                      onChange={(e) =>
                        patchDef(di, {
                          time_ranges: e.target.value
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                        })
                      }
                      aria-label={t("pgkit.segment_builder.time_ranges_aria")}
                    />
                    <p className="text-[10px] text-[var(--color-fog)]">
                      {t("pgkit.segment_builder.time_ranges_hint")}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3 border-t border-[var(--color-chalk)] pt-3">
            <button
              type="button"
              onClick={() => setDefs((d) => (d.length >= 10 ? d : [...d, emptyDef()]))}
              disabled={defs.length >= 10}
              className="inline-flex h-8 items-center gap-1.5 rounded-[8px] bg-[var(--color-powder)] px-4 text-[12px] text-[var(--color-gravel)] transition-colors hover:bg-[var(--color-chalk)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus size={13} /> {t("pgkit.segment_builder.add_def")}
            </button>
            <span className="text-[11px] text-[var(--color-fog)]">{t("pgkit.segment_builder.def_count", { count: defs.length })}</span>
          </div>
        </div>

        {/* RIGHT — Editor */}
        <div className="flex min-h-0 flex-col gap-3">
          <div className="text-[12px] font-semibold text-[var(--color-obsidian)]">{t("pgkit.segment_builder.editor_col")}</div>
          <pre
            className="flex-1 overflow-auto rounded-[16px] border border-[var(--color-chalk)] bg-[var(--color-powder)] p-4 font-mono text-[12px] leading-5 text-[var(--color-obsidian)]"
            aria-label={t("pgkit.segment_builder.json_preview_aria")}
          >
{JSON.stringify(
  defs.map((d) => ({
    id: d.id,
    description: d.description,
    fields: d.fields.map((f) => ({
      name: f.name,
      type: f.type,
      ...(f.description ? { description: f.description } : {}),
      ...(f.enum && f.enum.length ? { enum: f.enum } : {}),
    })),
    ...(d.time_ranges && d.time_ranges.length ? { time_ranges: d.time_ranges } : {}),
    ...(d.image_attachment ? { image_attachment: "<base64 image>" } : {}),
  })),
  null,
  2,
)}
          </pre>
        </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-[var(--color-chalk)] pt-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--color-chalk)] px-3 py-1.5 text-sm text-[var(--color-obsidian)] hover:bg-[var(--color-powder)] focus-visible:outline-2 focus-visible:outline-signal"
          >
            {t("actions.cancel")}
          </button>
          <button
            type="button"
            onClick={apply}
            className="rounded-lg bg-[var(--color-obsidian)] px-3 py-1.5 text-sm text-white transition duration-150 ease-out hover:opacity-90 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-signal"
          >
            {t("pgkit.segment_builder.apply")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default SegmentBuilderModal;

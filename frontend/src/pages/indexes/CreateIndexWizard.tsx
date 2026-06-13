import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { AudioWaveform, Check, Eye, Info, Sparkles, X, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";

import { addVideoToIndex, createIndex, type IndexSummary } from "@/apis/indexes.api";
import { uploadVideo } from "@/apis/videos.api";
import { cn } from "@/lib/utils";
import { VideoDropZone } from "./VideoDropZone";

function OptionCard({
  icon,
  label,
  checked,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label
      className={cn(
        "flex h-12 cursor-pointer items-center justify-between rounded-xl border px-4 transition-colors",
        checked
          ? "border-[var(--color-gravel)] bg-[var(--color-powder)]"
          : "border-[var(--color-chalk)] bg-white hover:border-[var(--color-slate)]",
      )}
    >
      <div className="flex items-center gap-x-2">
        {icon}
        <span className="text-[13px] text-[var(--color-obsidian)]">{label}</span>
      </div>
      <input
        type="checkbox"
        className="sr-only"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span
        className={cn(
          "grid h-5 w-5 place-items-center rounded-[6px] border transition-colors",
          checked
            ? "border-[var(--color-obsidian)] bg-[var(--color-obsidian)] text-white"
            : "border-[var(--color-chalk)] bg-white",
        )}
      >
        {checked && <Check size={13} strokeWidth={3} />}
      </span>
    </label>
  );
}

type UploadItem = { name: string; status: "uploading" | "done" | "error" };

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (summary: IndexSummary) => void;
}

export function CreateIndexWizard({ open, onClose, onCreated }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [name, setName] = useState("");
  const [visual, setVisual] = useState(true);
  const [audio, setAudio] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<IndexSummary | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const createdRef = useRef<IndexSummary | null>(null);

  if (!open) return null;

  const close = () => {
    setStep(1);
    setName("");
    setVisual(true);
    setAudio(true);
    setError(null);
    setCreated(null);
    setUploads([]);
    onClose();
  };

  const next = async () => {
    if (!name.trim()) {
      setError(t("console.index_wizard.error_name_required"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const summary = await createIndex({ title: name.trim() });
      createdRef.current = summary;
      setCreated(summary);
      onCreated(summary);
      setStep(2);
    } catch {
      setError(t("console.index_wizard.error_create_failed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleFiles = (files: File[]) => {
    const idx = createdRef.current;
    if (!idx) return;
    setUploads((prev) => [...prev, ...files.map((f) => ({ name: f.name, status: "uploading" as const }))]);
    files.forEach(async (f) => {
      try {
        const v = await uploadVideo(f);
        await addVideoToIndex(idx.id, v.id);
        setUploads((prev) => prev.map((u) => (u.name === f.name ? { ...u, status: "done" } : u)));
      } catch {
        setUploads((prev) => prev.map((u) => (u.name === f.name ? { ...u, status: "error" } : u)));
      }
    });
  };

  const finish = () => {
    const id = created?.id;
    close();
    if (id) navigate(`/indexes/${id}`);
  };

  const uploadsBusy = uploads.some((u) => u.status === "uploading");

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-6" onClick={close}>
      <div
        className="w-full max-w-[560px] rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between p-6 pb-4 tablet:px-8">
          <h6 className="flex-1 truncate text-[18px] font-medium text-[var(--color-obsidian)]">
            {t("console.index_wizard.title")}
          </h6>
          <div className="rounded-md border border-[var(--color-slate)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--color-slate)]">
            {step}/2
          </div>
        </div>

        {step === 1 ? (
          <>
            <div className="max-h-[calc(100dvh-240px)] overflow-y-auto px-6 tablet:px-8">
              <div className="flex flex-col gap-y-2">
                <label htmlFor="index_name" className="text-[13px] text-[var(--color-obsidian)]">
                  {t("console.index_wizard.set_name")}
                </label>
                <div className="flex h-10 items-center rounded-lg border border-[var(--color-chalk)] px-4 transition-colors focus-within:border-[var(--color-obsidian)] hover:border-[var(--color-slate)]">
                  <input
                    id="index_name"
                    autoFocus
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && next()}
                    placeholder={t("console.index_wizard.name_placeholder")}
                    className="h-full w-full border-none bg-transparent text-[13px] text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-slate)]"
                  />
                </div>
              </div>

              <div className="mt-6 flex items-center gap-x-1">
                <p className="text-[13px] text-[var(--color-obsidian)]">
                  {t("console.index_wizard.model_options")}
                </p>
                <Info size={15} className="text-[var(--color-slate)]" />
              </div>
              <p className="mt-2.5 text-[12px] text-[var(--color-gravel)]">
                {t("console.index_wizard.options_note")}
              </p>

              <div className="ml-3 mt-4 flex items-center gap-x-2">
                <Zap size={22} className="text-[var(--color-obsidian)]" />
                <p className="text-[14px] font-medium text-[var(--color-obsidian)]">
                  {t("console.index_wizard.marengo_name")}
                </p>
                <p className="text-[12px] text-[var(--color-gravel)]">
                  {t("console.index_wizard.marengo_caption")}
                </p>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-x-3">
                <OptionCard
                  icon={<Eye size={18} className="text-[var(--color-gravel)]" />}
                  label={t("console.index_wizard.option_visual")}
                  checked={visual}
                  onChange={setVisual}
                />
                <OptionCard
                  icon={<AudioWaveform size={18} className="text-[var(--color-gravel)]" />}
                  label={t("console.index_wizard.option_audio")}
                  checked={audio}
                  onChange={setAudio}
                />
              </div>

              <div className="mt-6 rounded-xl border border-[var(--color-chalk)] bg-[linear-gradient(90deg,#F4F3F3_43.7%,#FFD3BE_64.42%,#F6AE8A_79.52%,#F4A680_91.35%,#FABA17_99.89%)] p-4">
                <div className="flex gap-x-2">
                  <Sparkles size={20} className="min-w-5 text-[var(--color-obsidian)]" />
                  <div className="flex flex-col text-[12px] text-[var(--color-obsidian)]">
                    <p>{t("console.index_wizard.pegasus_line1")}</p>
                    <p>{t("console.index_wizard.pegasus_line2")}</p>
                    <div className="mt-2 flex items-center gap-x-3">
                      <Link to="/playground/analyze" className="underline hover:no-underline">
                        {t("console.index_wizard.try_analyze")}
                      </Link>
                      <Link to="/playground/segment" className="underline hover:no-underline">
                        {t("console.index_wizard.try_segment")}
                      </Link>
                    </div>
                  </div>
                </div>
              </div>

              {error && <p className="mt-3 text-[12px] text-rose-600">{error}</p>}
            </div>

            <div className="flex items-center justify-between p-6 tablet:p-8">
              <button
                type="button"
                onClick={close}
                className="rounded-[12px] px-[18px] py-2 text-[13px] text-[var(--color-obsidian)] shadow-[0px_0px_0px_1px_var(--color-chalk)_inset] transition-all hover:rounded-[16px] hover:bg-black/5"
              >
                {t("actions.cancel")}
              </button>
              <button
                type="button"
                onClick={next}
                disabled={submitting}
                className="rounded-[12px] bg-[var(--color-obsidian)] px-[18px] py-2 text-[13px] text-white transition-all hover:rounded-[16px] hover:bg-neutral-800 disabled:opacity-50"
              >
                {submitting ? t("console.index_wizard.creating") : t("console.index_wizard.next")}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="max-h-[calc(100dvh-240px)] overflow-y-auto px-6 tablet:px-8">
              <VideoDropZone onFiles={handleFiles} />
              {uploads.length > 0 && (
                <ul className="mt-4 flex flex-col gap-1.5">
                  {uploads.map((u, i) => (
                    <li
                      key={`${u.name}-${i}`}
                      className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-chalk)] px-3 py-2"
                    >
                      <span className="min-w-0 flex-1 truncate text-[12px] text-[var(--color-obsidian)]">
                        {u.name}
                      </span>
                      <span
                        className={cn(
                          "font-mono text-[11px]",
                          u.status === "done" && "text-emerald-600",
                          u.status === "error" && "text-rose-600",
                          u.status === "uploading" && "text-amber-600",
                        )}
                      >
                        {t(`console.index_wizard.upload_status_${u.status}`)}
                      </span>
                      {u.status === "error" && <X size={13} className="text-rose-600" />}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex items-center justify-end p-6 tablet:p-8">
              <button
                type="button"
                onClick={finish}
                disabled={uploadsBusy}
                className="rounded-[12px] bg-[var(--color-obsidian)] px-[18px] py-2 text-[13px] text-white transition-all hover:rounded-[16px] hover:bg-neutral-800 disabled:opacity-50"
              >
                {t("console.index_wizard.done")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

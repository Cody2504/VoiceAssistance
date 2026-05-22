import { UserSquare, Info } from "lucide-react";

export default function Entities() {
  return (
    <div className="mx-auto max-w-[1180px] px-8 py-6">
      <div className="mb-6 flex items-center gap-2">
        <h1 className="text-[32px] font-light tracking-[-0.64px] text-[var(--color-obsidian)]">
          Entities
        </h1>
        <Info size={14} className="text-[var(--color-slate)]" />
      </div>

      <div className="grid place-items-center rounded-[18px] border border-[var(--color-chalk)] bg-gradient-warm py-24 text-center">
        <UserSquare size={32} className="mb-3 text-[var(--color-obsidian)]/60" />
        <h2 className="text-[20px] font-medium text-[var(--color-obsidian)]">No entities detected yet</h2>
        <p className="mt-2 max-w-md px-6 text-[14px] text-[var(--color-gravel)]">
          Entities (people, products, locations) extracted from your indexed videos will appear here.
          Run an Analyze pass on a video to populate this page.
        </p>
      </div>
    </div>
  );
}

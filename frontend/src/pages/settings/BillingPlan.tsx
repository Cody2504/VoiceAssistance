import { Info, ArrowUpRight, MessageSquare } from "lucide-react";

/**
 * Billing & plan page reproducing the TwelveLabs dashboard:
 * - Free plan card with usage bar + max-duration / max-videos stats + Upgrade
 * - Payment card with Register-method button
 * - Total amount due (grey) with charge amount / billing period / charge date
 * - Billing history table (empty state)
 */
export default function BillingPlan() {
  return (
    <>
      {/* Free plan card */}
      <Section>
        <div className="flex items-center justify-between gap-12">
          <p className="flex-1 text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
            Free plan
          </p>
          <a
            href="#"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--color-obsidian)] hover:underline"
          >
            <MessageSquare size={16} /> Talk To Sales
          </a>
          <a
            href="#"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--color-obsidian)] hover:underline"
          >
            Pricing <ArrowUpRight size={14} />
          </a>
        </div>

        <Label label="Video hours usage" />
        <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
          6 min
          <span className="text-[var(--color-slate)]"> / 10 hr</span>
        </p>

        <div className="flex w-[550px] max-w-full flex-col gap-2">
          <div className="relative flex h-3 w-full items-center overflow-hidden rounded border border-[var(--color-obsidian)]">
            <span className="inline-block h-full" style={{ width: "0%" }}>
              <div className="h-full w-full bg-[#5fb364]" />
            </span>
            <span className="inline-block h-full" style={{ width: "1%" }}>
              <div className="h-full w-full bg-[#e5b659]" />
            </span>
          </div>
          <div className="flex items-center gap-3 text-[12px] text-[var(--color-obsidian)]">
            <span className="inline-flex items-center gap-1">
              <span aria-hidden className="inline-block h-2 w-2 rounded-[2px] border border-[var(--color-slate)] bg-[#5fb364]" />
              Indexing
            </span>
            <span className="inline-flex items-center gap-1">
              <span aria-hidden className="inline-block h-2 w-2 rounded-[2px] border border-[var(--color-slate)] bg-[#e5b659]" />
              Analyze &amp; Segment
            </span>
          </div>
        </div>

        <div className="flex gap-10">
          <div className="flex flex-col gap-2">
            <Label label="Max duration per index" />
            <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
              0 hr <span className="text-[16px] text-[var(--color-slate)]">/ 10 hr</span>
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label label="Max videos per index" />
            <p className="text-[24px] font-light tracking-[-0.4px] text-[var(--color-obsidian)]">
              0 videos <span className="text-[16px] text-[var(--color-slate)]">/ 100 videos</span>
            </p>
          </div>
        </div>

        <div className="pt-2">
          <button
            type="button"
            className="inline-flex h-10 items-center gap-1 rounded-[12px] bg-[var(--color-obsidian)] px-[18px] text-[14px] font-medium text-white transition-all hover:rounded-[16px] hover:bg-neutral-800"
          >
            Upgrade plan <ArrowUpRight size={14} />
          </button>
        </div>
      </Section>

      {/* Payment */}
      <Section>
        <SectionTitle>Payment</SectionTitle>
        <button
          type="button"
          className="inline-flex h-10 w-fit items-center gap-1 rounded-[12px] border border-[var(--color-obsidian)] bg-transparent px-[18px] text-[14px] font-medium text-[var(--color-obsidian)] transition-all hover:rounded-[16px] hover:bg-black/5"
        >
          Register payment method
        </button>
      </Section>

      {/* Total amount due (grey background) */}
      <Section grey>
        <SectionTitle>Total amount due</SectionTitle>
        <div className="flex gap-20">
          <Stat label="Charge amount" value="$0.00" />
          <Stat label="Billing period" value="May 1, 2026 ~ Jun 1, 2026" />
          <Stat label="Charge date" value="Jun 2, 2026" />
        </div>
      </Section>

      {/* Billing history */}
      <Section>
        <SectionTitle>Billing history</SectionTitle>
        <div className="overflow-hidden rounded-xl">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--color-chalk)] text-left">
                {[
                  "Issued date",
                  "Due date",
                  "Status",
                  "Total amount",
                  "Paid amount",
                  "Billing period",
                  "Invoice",
                  "Receipt",
                  "Usage details",
                ].map((h, i) => (
                  <th
                    key={h}
                    className={`whitespace-nowrap px-3 py-3 font-semibold text-[var(--color-obsidian)] ${i >= 6 ? "text-center" : "text-left"}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={9} className="py-10 text-center text-[var(--color-gravel)]">
                  No Billing History Data!
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

function Section({ children, grey }: { children: React.ReactNode; grey?: boolean }) {
  return (
    <section
      className={`flex w-full flex-col gap-6 rounded-[32px] border border-[var(--color-chalk)] p-9 ${
        grey ? "bg-[var(--color-powder)]" : "bg-white"
      }`}
    >
      {children}
    </section>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[18px] leading-8 text-[var(--color-obsidian)]">{children}</p>
  );
}

function Label({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1">
      <p className="text-[13px] text-[var(--color-gravel)]">{label}</p>
      <Info size={14} className="text-[var(--color-slate)]" />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-2">
      <Label label={label} />
      <p className="text-[14px] text-[var(--color-obsidian)]">{value}</p>
    </div>
  );
}

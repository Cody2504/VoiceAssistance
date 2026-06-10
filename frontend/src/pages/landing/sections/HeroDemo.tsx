import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { Search, MessageSquare, Layers, ArrowUpRight, CornerDownLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DEMO_DURATION,
  DEMO_FRAMES,
  DEMO_SEGMENTS,
  DEMO_QA,
  EXAMPLE_QUERY_KEYS,
  EXAMPLE_QUERIES_EN,
  fmtTime,
  searchMoments,
  tileForTime,
  type DemoMoment,
} from "../demoFixture";

type Tab = "search" | "chat" | "segment";

/** Synthetic filmstrip tiles, hue-coded by the segment they fall in. */
const TILES = Array.from({ length: DEMO_FRAMES }, (_, i) => {
  const t = (i / (DEMO_FRAMES - 1)) * DEMO_DURATION;
  const seg =
    DEMO_SEGMENTS.find((s) => t >= s.start && t < s.end) ??
    DEMO_SEGMENTS[DEMO_SEGMENTS.length - 1];
  return { i, t, hue: seg.hue };
});

function tileBg(hue: number, dim = false) {
  const l1 = dim ? 86 : 74;
  const l2 = dim ? 80 : 56;
  return `linear-gradient(135deg, hsl(${hue} 52% ${l1}%), hsl(${(hue + 26) % 360} 58% ${l2}%))`;
}

/**
 * Fixture-backed "try-before-signup" demo, layered inside the hero.
 * 100% client-side (see ../demoFixture) — no backend, no API key, no GPU.
 */
export function HeroDemo() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("search");

  const TABS: { id: Tab; labelKey: string; icon: React.ReactNode }[] = [
    { id: "search",  labelKey: "landing.hero_demo.tab_search",  icon: <Search size={15} /> },
    { id: "chat",    labelKey: "landing.hero_demo.tab_chat",    icon: <MessageSquare size={15} /> },
    { id: "segment", labelKey: "landing.hero_demo.tab_segment", icon: <Layers size={15} /> },
  ];

  // --- search state ---
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DemoMoment[] | null>(null);
  const matchedTiles = useMemo(
    () => new Set((results ?? []).map((m) => tileForTime(m.t))),
    [results]
  );

  function runSearch(q: string) {
    setQuery(q);
    setResults(searchMoments(q));
  }

  // --- chat state ---
  const [chatInput, setChatInput] = useState("");
  const [answer, setAnswer] = useState<(typeof DEMO_QA)[number] | null>(null);

  function ask(q: string) {
    setChatInput(q);
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    const best =
      DEMO_QA.map((qa) => ({
        qa,
        score: terms.reduce(
          (n, term) =>
            n + ((t(qa.qKey) + " " + t(qa.aKey)).toLowerCase().includes(term) ? 1 : 0),
          0
        ),
      })).sort((a, b) => b.score - a.score)[0];
    setAnswer(best && best.score > 0 ? best.qa : DEMO_QA[0]);
  }

  return (
    <div className="mx-auto mt-12 w-full max-w-[940px] text-left">
      <div className="overflow-hidden rounded-[24px] border border-[var(--color-chalk)] bg-white/90 shadow-[0_40px_90px_-45px_rgba(0,0,0,0.4)] backdrop-blur">
        {/* window chrome + tabs */}
        <div className="flex items-center gap-3 border-b border-[var(--color-chalk)] px-4 py-3">
          <span className="hidden gap-1.5 sm:flex" aria-hidden="true">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          </span>
          <span className="hidden text-[12px] text-[var(--color-slate)] sm:inline">
            champions-final.mp4 · 1:30
          </span>
          <div
            role="tablist"
            aria-label={t("landing.hero_demo.aria_tabs")}
            className="ml-auto flex items-center gap-1 rounded-full bg-[var(--color-powder)] p-1"
          >
            {TABS.map((tabItem) => (
              <button
                key={tabItem.id}
                role="tab"
                aria-selected={tab === tabItem.id}
                onClick={() => setTab(tabItem.id)}
                className={cn(
                  "inline-flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-medium transition",
                  tab === tabItem.id
                    ? "bg-[var(--color-obsidian)] text-white"
                    : "text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]"
                )}
              >
                {tabItem.icon}
                <span className="hidden sm:inline">{t(tabItem.labelKey)}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 sm:p-5">
          {/* ---------- SEARCH ---------- */}
          {tab === "search" && (
            <div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  runSearch(query);
                }}
                className="flex items-center gap-2 rounded-full border border-[var(--color-chalk)] bg-white px-4 py-2.5 focus-within:border-[var(--color-accent-blue)]"
              >
                <Search size={18} className="shrink-0 text-[var(--color-slate)]" />
                <label htmlFor="demo-q" className="sr-only">
                  {t("landing.hero_demo.search_label")}
                </label>
                <input
                  id="demo-q"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t("landing.hero_demo.search_placeholder")}
                  className="w-full bg-transparent text-[15px] text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-slate)]"
                />
                <button
                  type="submit"
                  className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full bg-[var(--color-accent-blue)] px-4 py-1.5 text-[13px] font-medium text-white transition hover:opacity-90"
                >
                  {t("landing.hero_demo.search_button")}
                </button>
              </form>

              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-[12px] text-[var(--color-slate)]">{t("landing.hero_demo.search_try")}</span>
                {EXAMPLE_QUERY_KEYS.map((qKey, idx) => (
                  <button
                    key={qKey}
                    onClick={() => runSearch(EXAMPLE_QUERIES_EN[idx])}
                    className="cursor-pointer rounded-full border border-[var(--color-chalk)] px-2.5 py-0.5 text-[12px] text-[var(--color-gravel)] transition hover:border-[var(--color-accent-blue)] hover:text-[var(--color-accent-blue)]"
                  >
                    {t(qKey)}
                  </button>
                ))}
              </div>

              <Filmstrip matched={matchedTiles} />

              <div className="mt-4 min-h-[60px]">
                {results === null && (
                  <p className="text-[13px] text-[var(--color-slate)]">
                    {t("landing.hero_demo.search_empty")}
                  </p>
                )}
                {results !== null && results.length === 0 && (
                  <p className="text-[13px] text-[var(--color-gravel)]">
                    {t("landing.hero_demo.search_no_results", { query })}
                  </p>
                )}
                {results !== null && results.length > 0 && (
                  <ul className="space-y-1.5">
                    {results.map((m) => (
                      <li
                        key={m.id}
                        className="flex items-center gap-3 rounded-lg border border-[var(--color-chalk)] bg-[var(--color-eggshell)] px-3 py-2"
                      >
                        <span className="inline-flex min-w-[44px] justify-center rounded-md bg-[var(--color-obsidian)] px-2 py-0.5 text-[12px] font-medium tabular-nums text-white">
                          {fmtTime(m.t)}
                        </span>
                        <span className="text-[14px] text-[var(--color-obsidian)]">
                          {t(m.labelKey)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {/* ---------- CHAT ---------- */}
          {tab === "chat" && (
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                {DEMO_QA.map((qa) => (
                  <button
                    key={qa.qKey}
                    onClick={() => ask(t(qa.qKey))}
                    className="cursor-pointer rounded-full border border-[var(--color-chalk)] px-3 py-1 text-[12px] text-[var(--color-gravel)] transition hover:border-[var(--color-accent-blue)] hover:text-[var(--color-accent-blue)]"
                  >
                    {t(qa.qKey)}
                  </button>
                ))}
              </div>

              <div className="min-h-[150px] space-y-3 rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)] p-3">
                {!answer && (
                  <p className="text-[13px] text-[var(--color-slate)]">
                    {t("landing.hero_demo.chat_empty")}
                  </p>
                )}
                {answer && (
                  <>
                    <div className="flex justify-end">
                      <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--color-obsidian)] px-3 py-2 text-[14px] text-white">
                        {t(answer.qKey)}
                      </p>
                    </div>
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[var(--color-chalk)] bg-white px-3 py-2">
                        <p className="text-[14px] text-[var(--color-obsidian)]">{t(answer.aKey)}</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {answer.cites.map((c) => (
                            <span
                              key={c}
                              className="inline-flex items-center rounded-md bg-[var(--color-powder)] px-2 py-0.5 text-[11px] font-medium tabular-nums text-[var(--color-gravel)]"
                            >
                              {fmtTime(c)}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (chatInput.trim()) ask(chatInput);
                }}
                className="mt-3 flex items-center gap-2 rounded-full border border-[var(--color-chalk)] bg-white px-4 py-2.5 focus-within:border-[var(--color-accent-blue)]"
              >
                <label htmlFor="demo-chat" className="sr-only">
                  {t("landing.hero_demo.chat_label")}
                </label>
                <input
                  id="demo-chat"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder={t("landing.hero_demo.chat_placeholder")}
                  className="w-full bg-transparent text-[15px] text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-slate)]"
                />
                <button
                  type="submit"
                  aria-label={t("landing.hero_demo.chat_send")}
                  className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full bg-[var(--color-accent-blue)] px-3 py-1.5 text-[13px] font-medium text-white transition hover:opacity-90"
                >
                  <CornerDownLeft size={15} />
                </button>
              </form>
            </div>
          )}

          {/* ---------- SEGMENT ---------- */}
          {tab === "segment" && (
            <div>
              <Filmstrip matched={new Set()} solid />
              {/* proportional segment bar */}
              <div className="mt-4 flex overflow-hidden rounded-lg">
                {DEMO_SEGMENTS.map((s) => (
                  <div
                    key={s.id}
                    className="flex h-9 items-center justify-center text-[11px] font-medium text-[var(--color-obsidian)]/80"
                    style={{
                      width: `${((s.end - s.start) / DEMO_DURATION) * 100}%`,
                      background: tileBg(s.hue),
                    }}
                    title={`${t(s.labelKey)} · ${fmtTime(s.start)}–${fmtTime(s.end)}`}
                  >
                    <span className="truncate px-1">{t(s.labelKey)}</span>
                  </div>
                ))}
              </div>
              <ul className="mt-4 space-y-1.5">
                {DEMO_SEGMENTS.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-center gap-3 rounded-lg border border-[var(--color-chalk)] bg-[var(--color-eggshell)] px-3 py-2"
                  >
                    <span
                      className="h-3 w-3 shrink-0 rounded-full"
                      style={{ background: `hsl(${s.hue} 60% 55%)` }}
                    />
                    <span className="inline-flex min-w-[84px] justify-center rounded-md bg-[var(--color-obsidian)] px-2 py-0.5 text-[12px] font-medium tabular-nums text-white">
                      {fmtTime(s.start)}–{fmtTime(s.end)}
                    </span>
                    <span className="text-[14px] text-[var(--color-obsidian)]">{t(s.labelKey)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[12px] text-[var(--color-slate)]">
                {t("landing.hero_demo.segment_footer")}
              </p>
            </div>
          )}

          {/* footer CTA — consistent across tabs */}
          <div className="mt-5 flex items-center justify-between border-t border-[var(--color-chalk)] pt-4">
            <p className="text-[12px] text-[var(--color-slate)]">
              {t("landing.hero_demo.footer_sample")}
            </p>
            <Link
              to="/signup"
              className="inline-flex cursor-pointer items-center gap-1 text-[13px] font-medium text-[var(--color-accent-blue)] transition hover:gap-1.5"
            >
              {t("landing.hero_demo.footer_upload")} <ArrowUpRight size={15} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Row of hue-coded frame tiles; `matched` highlights search hits. */
function Filmstrip({ matched, solid = false }: { matched: Set<number>; solid?: boolean }) {
  return (
    <div className="mt-4 flex gap-1.5">
      {TILES.map((tile) => {
        const isHit = matched.has(tile.i);
        return (
          <div
            key={tile.i}
            className={cn(
              "relative aspect-[16/11] flex-1 rounded-md transition-all duration-200",
              isHit
                ? "-translate-y-1 ring-2 ring-[var(--color-accent-blue)]"
                : "ring-1 ring-black/5"
            )}
            style={{ background: tileBg(tile.hue, !solid && matched.size > 0 && !isHit) }}
            title={fmtTime(tile.t)}
          >
            {isHit && (
              <span className="absolute -top-1.5 left-1/2 h-2 w-2 -translate-x-1/2 rounded-full bg-[var(--color-accent-blue)]" />
            )}
          </div>
        );
      })}
    </div>
  );
}

import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Search, MessageSquare, Layers, ArrowUpRight, CornerDownLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DEMO_DURATION,
  DEMO_FRAMES,
  DEMO_SEGMENTS,
  DEMO_QA,
  EXAMPLE_QUERIES,
  fmtTime,
  searchMoments,
  tileForTime,
  type DemoMoment,
} from "../demoFixture";

type Tab = "search" | "chat" | "segment";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "search", label: "Search", icon: <Search size={15} /> },
  { id: "chat", label: "Chat / QA", icon: <MessageSquare size={15} /> },
  { id: "segment", label: "Segment", icon: <Layers size={15} /> },
];

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
  const [tab, setTab] = useState<Tab>("search");

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
          (n, t) => n + ((qa.q + " " + qa.a).toLowerCase().includes(t) ? 1 : 0),
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
            aria-label="Demo capability"
            className="ml-auto flex items-center gap-1 rounded-full bg-[var(--color-powder)] p-1"
          >
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "inline-flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-medium transition",
                  tab === t.id
                    ? "bg-[var(--color-obsidian)] text-white"
                    : "text-[var(--color-gravel)] hover:text-[var(--color-obsidian)]"
                )}
              >
                {t.icon}
                <span className="hidden sm:inline">{t.label}</span>
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
                  Search the sample video
                </label>
                <input
                  id="demo-q"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search this video in natural language…"
                  className="w-full bg-transparent text-[15px] text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-slate)]"
                />
                <button
                  type="submit"
                  className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full bg-[var(--color-accent-blue)] px-4 py-1.5 text-[13px] font-medium text-white transition hover:opacity-90"
                >
                  Search
                </button>
              </form>

              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-[12px] text-[var(--color-slate)]">Try:</span>
                {EXAMPLE_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => runSearch(q)}
                    className="cursor-pointer rounded-full border border-[var(--color-chalk)] px-2.5 py-0.5 text-[12px] text-[var(--color-gravel)] transition hover:border-[var(--color-accent-blue)] hover:text-[var(--color-accent-blue)]"
                  >
                    {q}
                  </button>
                ))}
              </div>

              <Filmstrip matched={matchedTiles} />

              <div className="mt-4 min-h-[60px]">
                {results === null && (
                  <p className="text-[13px] text-[var(--color-slate)]">
                    Type a query or tap an example — matching moments light up on the
                    timeline above.
                  </p>
                )}
                {results !== null && results.length === 0 && (
                  <p className="text-[13px] text-[var(--color-gravel)]">
                    No moments matched “{query}”. Try <em>goal</em>, <em>celebration</em>,
                    or <em>trophy</em>.
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
                          {m.label}
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
                    key={qa.q}
                    onClick={() => ask(qa.q)}
                    className="cursor-pointer rounded-full border border-[var(--color-chalk)] px-3 py-1 text-[12px] text-[var(--color-gravel)] transition hover:border-[var(--color-accent-blue)] hover:text-[var(--color-accent-blue)]"
                  >
                    {qa.q}
                  </button>
                ))}
              </div>

              <div className="min-h-[150px] space-y-3 rounded-xl border border-[var(--color-chalk)] bg-[var(--color-eggshell)] p-3">
                {!answer && (
                  <p className="text-[13px] text-[var(--color-slate)]">
                    Ask a question about the sample clip — pick one above or type your own.
                  </p>
                )}
                {answer && (
                  <>
                    <div className="flex justify-end">
                      <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--color-obsidian)] px-3 py-2 text-[14px] text-white">
                        {answer.q}
                      </p>
                    </div>
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[var(--color-chalk)] bg-white px-3 py-2">
                        <p className="text-[14px] text-[var(--color-obsidian)]">{answer.a}</p>
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
                  Ask about the sample video
                </label>
                <input
                  id="demo-chat"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask about the sample video…"
                  className="w-full bg-transparent text-[15px] text-[var(--color-obsidian)] outline-none placeholder:text-[var(--color-slate)]"
                />
                <button
                  type="submit"
                  aria-label="Send"
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
                    title={`${s.label} · ${fmtTime(s.start)}–${fmtTime(s.end)}`}
                  >
                    <span className="truncate px-1">{s.label}</span>
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
                    <span className="text-[14px] text-[var(--color-obsidian)]">{s.label}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[12px] text-[var(--color-slate)]">
                Auto-detected with shot detection, ASR & topic-change segmentation.
              </p>
            </div>
          )}

          {/* footer CTA — consistent across tabs */}
          <div className="mt-5 flex items-center justify-between border-t border-[var(--color-chalk)] pt-4">
            <p className="text-[12px] text-[var(--color-slate)]">
              Sample video · runs entirely in your browser
            </p>
            <Link
              to="/signup"
              className="inline-flex cursor-pointer items-center gap-1 text-[13px] font-medium text-[var(--color-accent-blue)] transition hover:gap-1.5"
            >
              Upload your own video <ArrowUpRight size={15} />
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

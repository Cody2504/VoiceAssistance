/**
 * Static fixture powering the guest "try-before-signup" hero demo.
 *
 * Everything here is client-side only — no backend, no API key, no GPU.
 * It lets a logged-out visitor experience semantic search / QA / segmentation
 * on a sample video, mirroring the ElevenLabs "interactive demo in the hero"
 * pattern. When a real read-only search endpoint exists, swap `searchMoments`
 * for a fetch — the component contract stays identical.
 *
 * User-visible strings (label, q, a) are stored as i18n keys so that
 * HeroDemo.tsx can resolve them with t(). The `keywords` array and
 * search logic remain in English for the toy keyword matcher.
 */

export interface DemoMoment {
  id: string;
  /** seconds into the clip */
  t: number;
  /** i18n key for the display label */
  labelKey: string;
  /** terms that should surface this moment for a natural-language query */
  keywords: string[];
  /** hue (0–360) for the synthetic filmstrip tile */
  hue: number;
}

export interface DemoSegment {
  id: string;
  start: number;
  end: number;
  /** i18n key for the display label */
  labelKey: string;
  hue: number;
}

export interface DemoQA {
  /** i18n key for the question */
  qKey: string;
  /** i18n key for the answer */
  aKey: string;
  /** moment timestamps cited by the answer */
  cites: number[];
}

/** Sample clip length in seconds (a ~90s football-final highlight). */
export const DEMO_DURATION = 90;

/** Number of synthetic frames rendered in the filmstrip. */
export const DEMO_FRAMES = 16;

export const DEMO_MOMENTS: DemoMoment[] = [
  { id: "m1", t: 3,  labelKey: "landing.demo_fixture.m1_label", keywords: ["kickoff", "kick off", "start", "whistle", "begin"], hue: 150 },
  { id: "m2", t: 17, labelKey: "landing.demo_fixture.m2_label", keywords: ["pass", "midfield", "build up", "dribble", "possession"], hue: 130 },
  { id: "m3", t: 34, labelKey: "landing.demo_fixture.m3_label", keywords: ["shot", "strike", "attempt", "shoots"], hue: 40 },
  { id: "m4", t: 42, labelKey: "landing.demo_fixture.m4_label", keywords: ["goal", "scores", "score", "net", "top corner"], hue: 18 },
  { id: "m5", t: 49, labelKey: "landing.demo_fixture.m5_label", keywords: ["celebration", "celebrate", "cheer", "hug", "happy"], hue: 280 },
  { id: "m6", t: 58, labelKey: "landing.demo_fixture.m6_label", keywords: ["crowd", "fans", "cheering", "stadium", "noise"], hue: 320 },
  { id: "m7", t: 71, labelKey: "landing.demo_fixture.m7_label", keywords: ["whistle", "final", "end", "full time", "finish"], hue: 200 },
  { id: "m8", t: 82, labelKey: "landing.demo_fixture.m8_label", keywords: ["trophy", "lift", "win", "champions", "cup", "confetti"], hue: 48 },
];

export const DEMO_SEGMENTS: DemoSegment[] = [
  { id: "s1", start: 0,  end: 30, labelKey: "landing.demo_fixture.s1_label", hue: 145 },
  { id: "s2", start: 30, end: 46, labelKey: "landing.demo_fixture.s2_label", hue: 22 },
  { id: "s3", start: 46, end: 66, labelKey: "landing.demo_fixture.s3_label", hue: 290 },
  { id: "s4", start: 66, end: 90, labelKey: "landing.demo_fixture.s4_label", hue: 48 },
];

export const DEMO_QA: DemoQA[] = [
  { qKey: "landing.demo_fixture.qa1_q", aKey: "landing.demo_fixture.qa1_a", cites: [71, 82] },
  { qKey: "landing.demo_fixture.qa2_q", aKey: "landing.demo_fixture.qa2_a", cites: [42, 49] },
  { qKey: "landing.demo_fixture.qa3_q", aKey: "landing.demo_fixture.qa3_a", cites: [58] },
];

/** i18n keys for the example query chips shown in the search tab. */
export const EXAMPLE_QUERY_KEYS = [
  "landing.demo_fixture.eq1",
  "landing.demo_fixture.eq2",
  "landing.demo_fixture.eq3",
  "landing.demo_fixture.eq4",
];

/**
 * English keyword strings used by the toy matcher — kept separate from the
 * display keys so the matcher always works regardless of UI language.
 */
export const EXAMPLE_QUERIES_EN = ["the goal", "celebration", "trophy lift", "crowd cheering"];

/** mm:ss formatter for timestamps. */
export function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * Toy "semantic" search: lowercase token overlap against each moment's
 * keywords + labelKey. Good enough to feel responsive in a demo; deterministic
 * and dependency-free. Returns moments sorted by score (desc).
 */
export function searchMoments(query: string): DemoMoment[] {
  const q = query.toLowerCase().trim();
  if (!q) return [];
  const terms = q.split(/\s+/).filter(Boolean);
  const scored = DEMO_MOMENTS.map((m) => {
    const hay = m.keywords.join(" ").toLowerCase();
    let score = 0;
    for (const term of terms) {
      if (hay.includes(term)) score += 2;
      else if (term.length > 3 && hay.includes(term.slice(0, term.length - 1))) score += 1; // loose stem
    }
    // whole-phrase bonus
    if (m.keywords.some((k) => k.includes(q) || q.includes(k))) score += 3;
    return { m, score };
  });
  return scored
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.m);
}

/** Nearest filmstrip tile index for a given timestamp. */
export function tileForTime(t: number): number {
  return Math.round((t / DEMO_DURATION) * (DEMO_FRAMES - 1));
}

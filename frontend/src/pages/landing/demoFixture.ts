/**
 * Static fixture powering the guest "try-before-signup" hero demo.
 *
 * Everything here is client-side only — no backend, no API key, no GPU.
 * It lets a logged-out visitor experience semantic search / QA / segmentation
 * on a sample video, mirroring the ElevenLabs "interactive demo in the hero"
 * pattern. When a real read-only search endpoint exists, swap `searchMoments`
 * for a fetch — the component contract stays identical.
 */

export interface DemoMoment {
  id: string;
  /** seconds into the clip */
  t: number;
  label: string;
  /** terms that should surface this moment for a natural-language query */
  keywords: string[];
  /** hue (0–360) for the synthetic filmstrip tile */
  hue: number;
}

export interface DemoSegment {
  id: string;
  start: number;
  end: number;
  label: string;
  hue: number;
}

export interface DemoQA {
  q: string;
  a: string;
  /** moment timestamps cited by the answer */
  cites: number[];
}

/** Sample clip length in seconds (a ~90s football-final highlight). */
export const DEMO_DURATION = 90;

/** Number of synthetic frames rendered in the filmstrip. */
export const DEMO_FRAMES = 16;

export const DEMO_MOMENTS: DemoMoment[] = [
  { id: "m1", t: 3, label: "Kick-off", keywords: ["kickoff", "kick off", "start", "whistle", "begin"], hue: 150 },
  { id: "m2", t: 17, label: "Midfield build-up", keywords: ["pass", "midfield", "build up", "dribble", "possession"], hue: 130 },
  { id: "m3", t: 34, label: "Shot on goal", keywords: ["shot", "strike", "attempt", "shoots"], hue: 40 },
  { id: "m4", t: 42, label: "GOAL — top corner", keywords: ["goal", "scores", "score", "net", "top corner"], hue: 18 },
  { id: "m5", t: 49, label: "Celebration", keywords: ["celebration", "celebrate", "cheer", "hug", "happy"], hue: 280 },
  { id: "m6", t: 58, label: "Crowd roars", keywords: ["crowd", "fans", "cheering", "stadium", "noise"], hue: 320 },
  { id: "m7", t: 71, label: "Final whistle", keywords: ["whistle", "final", "end", "full time", "finish"], hue: 200 },
  { id: "m8", t: 82, label: "Trophy lift", keywords: ["trophy", "lift", "win", "champions", "cup", "confetti"], hue: 48 },
];

export const DEMO_SEGMENTS: DemoSegment[] = [
  { id: "s1", start: 0, end: 30, label: "Build-up", hue: 145 },
  { id: "s2", start: 30, end: 46, label: "The goal", hue: 22 },
  { id: "s3", start: 46, end: 66, label: "Celebration", hue: 290 },
  { id: "s4", start: 66, end: 90, label: "Trophy & wrap-up", hue: 48 },
];

export const DEMO_QA: DemoQA[] = [
  { q: "What happens at the end of the video?", a: "The match finishes at the final whistle (1:11) and the winning side lifts the trophy as confetti falls over the pitch (1:22).", cites: [71, 82] },
  { q: "Is there a goal? When?", a: "Yes — a single goal is scored into the top corner at 0:42, immediately followed by the players' celebration at 0:49.", cites: [42, 49] },
  { q: "Describe the crowd.", a: "After the goal the camera cuts to the stands where the crowd roars and fans celebrate (0:58).", cites: [58] },
];

export const EXAMPLE_QUERIES = ["the goal", "celebration", "trophy lift", "crowd cheering"];

/** mm:ss formatter for timestamps. */
export function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * Toy "semantic" search: lowercase token overlap against each moment's
 * keywords + label. Good enough to feel responsive in a demo; deterministic
 * and dependency-free. Returns moments sorted by score (desc).
 */
export function searchMoments(query: string): DemoMoment[] {
  const q = query.toLowerCase().trim();
  if (!q) return [];
  const terms = q.split(/\s+/).filter(Boolean);
  const scored = DEMO_MOMENTS.map((m) => {
    const hay = (m.label + " " + m.keywords.join(" ")).toLowerCase();
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

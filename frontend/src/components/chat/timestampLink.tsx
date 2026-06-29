import type { ReactNode } from "react";
import type { Components } from "react-markdown";

// [mm:ss] or [mm:ss-mm:ss] (hyphen or en-dash) — the citation format the agent
// emits (video-service analyze.py `_fmt` + reflect.md). Global flag for replace.
const TS_RE = /\[(\d{1,2}):(\d{2})(?:\s*[-–]\s*(\d{1,2}):(\d{2}))?\]/g;

/**
 * Rewrite `[mm:ss-mm:ss]` citations into markdown links `[label](#seek-<startSec>)`
 * so a custom <a> renderer can turn them into click-to-seek chips. Leaves the
 * rest of the markdown untouched.
 */
export function linkifyTimestamps(md: string): string {
  if (!md) return md;
  return md.replace(TS_RE, (_full, m1, s1, m2, s2) => {
    const start = parseInt(m1, 10) * 60 + parseInt(s1, 10);
    const label = m2 != null ? `${m1}:${s1}–${m2}:${s2}` : `${m1}:${s1}`;
    return `[${label}](#seek-${start})`;
  });
}

/**
 * ReactMarkdown `components` that render `#seek-<sec>` links as click-to-seek
 * chips (calling `onSeek`) and leave real links as normal external links.
 */
export function seekMarkdownComponents(onSeek?: (sec: number) => void): Components {
  return {
    a({ href, children }) {
      if (typeof href === "string" && href.startsWith("#seek-")) {
        const sec = parseInt(href.slice("#seek-".length), 10);
        return (
          <button
            type="button"
            onClick={() => onSeek?.(sec)}
            className="mx-0.5 rounded bg-emerald-50 px-1 font-medium text-emerald-700 tabular-nums hover:bg-emerald-100"
          >
            {children as ReactNode}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer" className="text-emerald-700 underline">
          {children as ReactNode}
        </a>
      );
    },
  };
}

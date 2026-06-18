import { useEffect, useState } from "react";

import { getIndexUsage } from "@/apis/usage.api";
import { getSubscription } from "@/apis/billing.api";

/**
 * Shared usage figures for the top-bar chip and the user menu: index-minutes
 * used this month (from the video-service index-usage endpoint) and the plan's
 * monthly cap (from the subscription; null = unlimited). Best-effort — both
 * default to a safe value if their request fails.
 */
export function useIndexUsage(): { usedMinutes: number; capMinutes: number | null } {
  const [usedMinutes, setUsedMinutes] = useState(0);
  const [capMinutes, setCapMinutes] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    getIndexUsage()
      .then((u) => {
        if (alive) setUsedMinutes(u.used_minutes || 0);
      })
      .catch(() => {});
    getSubscription()
      .then((s) => {
        if (alive) setCapMinutes(s?.plan?.monthly_index_minutes ?? null);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return { usedMinutes, capMinutes };
}

/** "1.9 hr" / "45 min" / the `unlimited` label when the cap is null. */
export function usageLabel(minutes: number | null | undefined, unlimited: string): string {
  if (minutes == null) return unlimited;
  return minutes >= 60 ? `${+(minutes / 60).toFixed(1)} hr` : `${Math.round(minutes)} min`;
}

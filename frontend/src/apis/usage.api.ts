import axios from "axios";
import { ROUTES } from "@/constants/routes";

export interface UsageDay {
  day: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}

export async function getMyUsage(): Promise<{ days: UsageDay[] }> {
  const r = await axios.get(ROUTES.USAGE_ME);
  return r.data?.data;
}

export interface IndexUsage {
  used_minutes: number;
  period_start: string;
  period_end: string;
}

export async function getIndexUsage(): Promise<IndexUsage> {
  const r = await axios.get(ROUTES.INDEX_USAGE);
  return r.data?.data;
}

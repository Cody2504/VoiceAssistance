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
